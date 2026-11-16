"""Dịch vụ local cho giao diện hỏi tài liệu; key chỉ được đọc ở backend."""
import json
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .agent import run_agent
from .day6_connection import Day6Connection
from .deepseek_client import DeepSeekClient, load_api_key
from .retrieval import validate_filters
from .retriever_service import RetrieverService

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def validate_request(payload):
    if not isinstance(payload, dict) or set(payload) - {"question", "configuration", "filter"}:
        raise ValueError("Chỉ nhận câu hỏi, cấu hình và phạm vi tìm kiếm.")
    if not isinstance(payload.get("question"), str) or not 1 <= len(payload["question"].strip()) <= 2000:
        raise ValueError("Nhập câu hỏi từ 1 đến 2.000 ký tự.")
    if payload.get("configuration", "selected") not in {"selected", "baseline", "tfidf", "hybrid", "dense-wide"}:
        raise ValueError("Cấu hình không hợp lệ.")
    validate_filters(payload.get("filter", {}))


class Application:
    def __init__(self, source):
        self.source = source
        self.connection = None
        self.service = None
        self.lock = threading.Lock()
        self.chunks = read(ROOT / "starter/data/day6/chunks.json")
        self.manifest = read(ROOT / "starter/data/day6/manifest.json")

    def selected(self):
        path = ROOT / "results/study/selection.json"
        return read(path)["selected_configuration"] if path.exists() else "baseline"

    def status(self):
        try:
            load_api_key(ROOT / ".env")
            configured = True
        except ValueError:
            configured = False
        return {"api_key_configured": configured, "model": "DeepSeek Flash", "model_ready": self.connection is not None,
                "busy": self.lock.locked(), "pages": self.manifest["included_content_pages"],
                "chunks": len(self.chunks), "selected_configuration": self.selected()}

    def examples(self):
        ids = {"q01", "q09", "dev_no_evidence_01"}
        return [row for row in read(ROOT / "benchmark/dev_queries.json") if row["id"] in ids]

    def results(self):
        result = {"selected": self.selected(), "label_origin": "DeepSeek chấm tự động; cần rà nguồn trước khi nộp."}
        for split in ("dev", "test"):
            path = ROOT / f"results/study/{split}_comparison.json"
            result[split] = read(path) if path.exists() else []
        return result

    def ask(self, payload):
        validate_request(payload)
        if not self.lock.acquire(blocking=False):
            raise RuntimeError("Đang xử lý một câu hỏi. Vui lòng chờ kết quả.")
        client = None
        started = time.perf_counter()
        try:
            key = load_api_key(ROOT / ".env")
            identifier = payload.get("configuration", "selected")
            identifier = self.selected() if identifier == "selected" else identifier
            path = ROOT / "config/experiments" / ("baseline.json" if identifier == "tfidf" else identifier + ".json")
            config = read(path)
            if identifier == "tfidf":
                config["retrieval_method"] = "tfidf"
            if self.connection is None:
                self.connection = Day6Connection(self.source, self.chunks, self.manifest)
                self.service = RetrieverService(self.connection, self.chunks, read(ROOT / "config/retrieval.json"))
            client = DeepSeekClient(config, key)
            query = {"id": "web_" + uuid.uuid4().hex, "split": "dev", "question": payload["question"].strip(),
                     "filter": payload.get("filter", {})}
            trace = run_agent(query, client, self.service, config)
            trace.update(origin="web_manual", configuration=identifier, api_requests=client.api_requests,
                         estimated_cost_upper_usd=client.estimated_cost_upper_usd,
                         request_elapsed_seconds=time.perf_counter() - started)
            output = ROOT / "results/web"
            output.mkdir(parents=True, exist_ok=True)
            (output / (query["id"] + ".json")).write_text(json.dumps(trace, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            lookup = {chunk["id"]: chunk for chunk in self.chunks}
            return {"status": trace["status"], "answer": trace["answer"], "reason": trace.get("abstention_reason", trace.get("error", "")),
                    "sources": [{**lookup[identifier]} for identifier in trace["citations"]],
                    "searches": [{"query": event["query"], "count": len(event.get("results", [])),
                                  "pages": sorted({row["page"] for row in event.get("results", [])})}
                                 for event in trace["events"] if event["event"] == "search"],
                    "api_requests": client.api_requests, "elapsed_seconds": trace["request_elapsed_seconds"],
                    "estimated_cost_upper_usd": client.estimated_cost_upper_usd, "configuration": identifier}
        finally:
            if client is not None:
                client.close()
            self.lock.release()

    def close(self):
        if self.connection is not None:
            self.connection.close()
