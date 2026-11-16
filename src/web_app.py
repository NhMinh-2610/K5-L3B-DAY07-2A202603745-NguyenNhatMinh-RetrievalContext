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
from .context_retriever import NeighborRetriever
from .document_store import DocumentStore, DocumentRetriever
from .vision_client import VisionClient
from .advanced_agent import run_agent as run_advanced_agent

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def validate_request(payload):
    if not isinstance(payload, dict) or set(payload) - {"question", "configuration", "filter", "dataset"}:
        raise ValueError("Chỉ nhận câu hỏi, cấu hình và phạm vi tìm kiếm.")
    if not isinstance(payload.get("question"), str) or not 1 <= len(payload["question"].strip()) <= 2000:
        raise ValueError("Nhập câu hỏi từ 1 đến 2.000 ký tự.")
    if payload.get("dataset", "basic") not in {"basic", "advanced"}:
        raise ValueError("Tài liệu không hợp lệ.")
    if payload.get("configuration", "selected") not in {"selected", "baseline", "tfidf", "hybrid", "dense-wide", "neighbors-1", "neighbors-2", "reference-text", "reference-8", "reference-12"}:
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
        self.book = None

    def selected(self, dataset="basic"):
        path = ROOT / ("results/extension/advanced-v2/selection.json" if dataset=="advanced" else "results/extension/basic-v2/selection.json")
        return read(path)["selected_configuration"] if path.exists() else "baseline"

    def status(self):
        try:
            load_api_key(ROOT / ".env")
            configured = True
        except ValueError:
            configured = False
        advanced_path=ROOT/"starter/data/advanced/manifest.json"
        advanced=read(advanced_path) if advanced_path.exists() else {}
        return {"api_key_configured": configured, "model": "DeepSeek Flash", "model_ready": self.connection is not None,
                "busy": self.lock.locked(), "pages": self.manifest["included_content_pages"],
                "chunks": len(self.chunks), "selected_configuration": self.selected(),
                "datasets":{"basic":{"pages":self.manifest["included_content_pages"],"chunks":len(self.chunks)},
                            "advanced":{"pages":advanced.get("physical_pages",0),"chunks":advanced.get("chunks",0)}}}

    def examples(self, dataset="basic"):
        if dataset=="advanced":
            return [r for r in read(ROOT/"benchmark/advanced/dev_queries.json") if r["id"] in {"ad_t2","ad_c2","ad_n1"}]
        ids = {"q01", "q09", "dev_no_evidence_01"}
        return [row for row in read(ROOT / "benchmark/dev_queries.json") if row["id"] in ids]

    def results(self, dataset="basic"):
        result = {"selected": self.selected(dataset), "dataset":dataset, "label_origin": "Nhãn API và đối chiếu nguồn; cần xác nhận trước khi nộp."}
        for split in ("dev", "test"):
            scope="advanced-v2" if dataset=="advanced" else "basic-v2"
            path = ROOT / f"results/extension/{scope}/{split}_comparison.json"
            reviewed=path.with_name(f"{split}_reviewed_comparison.json")
            if reviewed.exists():path=reviewed
            result[split] = read(path) if path.exists() else []
        return result

    def page_image(self, page):
        if type(page) is not int or not 1 <= page <= 356:
            raise ValueError("Trang phải từ 1 đến 356.")
        import fitz
        with fitz.open(ROOT/"starter/data/advanced/raw/nasa-systems-engineering-handbook-2016.pdf") as doc:
            return doc[page-1].get_pixmap(matrix=fitz.Matrix(1.4,1.4)).tobytes("jpg",jpg_quality=80)

    def ask(self, payload):
        validate_request(payload)
        if not self.lock.acquire(blocking=False):
            raise RuntimeError("Đang xử lý một câu hỏi. Vui lòng chờ kết quả.")
        client = None
        started = time.perf_counter()
        try:
            key = load_api_key(ROOT / ".env")
            dataset=payload.get("dataset","basic")
            identifier = payload.get("configuration", "selected")
            identifier = self.selected(dataset) if identifier == "selected" else identifier
            if dataset=="advanced":
                plan=read(ROOT/"config/advanced.json")["configurations"]
                if identifier not in plan:raise ValueError("Chọn cấu hình NASA phù hợp.")
                spec=plan[identifier];config={**read(ROOT/"config/agent.json"),**spec["agent"],"max_output_tokens":1200}
                if self.book is None:self.book=DocumentStore(ROOT/"starter/data/advanced",self.source)
                service=DocumentRetriever(self.book,anchored=spec["anchors"]).for_question(payload["question"])
                chunks=self.book.chunks
                client=VisionClient(config,key,chunks,ROOT/"starter/data/advanced") if spec["vision"] else DeepSeekClient(config,key)
                runner=run_advanced_agent
            else:
                if self.connection is None:
                    self.connection=Day6Connection(self.source,self.chunks,self.manifest)
                    self.service=RetrieverService(self.connection,self.chunks,read(ROOT/"config/retrieval.json"))
                plan=read(ROOT/"config/basic-v2.json")["configurations"]
                if identifier in plan:
                    spec=plan[identifier];config={**read(ROOT/"config/agent.json"),**spec["agent"]}
                    service=NeighborRetriever(self.service,self.chunks,spec["radius"]) if spec["radius"] else self.service
                    chunks=service.chunks if spec["radius"] else self.chunks
                else:
                    path=ROOT/"config/experiments"/("baseline.json" if identifier=="tfidf" else identifier+".json")
                    if not path.exists():raise ValueError("Chọn cấu hình Day 6 phù hợp.")
                    config=read(path)
                    if identifier=="tfidf":config["retrieval_method"]="tfidf"
                    service=self.service;chunks=self.chunks
                client=DeepSeekClient(config,key);runner=run_agent
            query = {"id": "web_" + uuid.uuid4().hex, "split": "dev", "question": payload["question"].strip(),
                     "filter": payload.get("filter", {})}
            trace = runner(query, client, service, config)
            trace.update(origin="web_manual", dataset=dataset, configuration=identifier, api_requests=client.api_requests,
                         estimated_cost_upper_usd=client.estimated_cost_upper_usd,
                         request_elapsed_seconds=time.perf_counter() - started)
            output = ROOT / "results/web"
            output.mkdir(parents=True, exist_ok=True)
            (output / (query["id"] + ".json")).write_text(json.dumps(trace, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            lookup = {chunk["id"]: chunk for chunk in chunks}
            return {"status": trace["status"], "answer": trace["answer"], "reason": trace.get("abstention_reason", trace.get("error", "")),
                    "sources": [{**lookup[identifier],"page_image":f"/api/page?page={lookup[identifier]['page']}" if dataset=="advanced" else None} for identifier in trace["citations"]],
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
