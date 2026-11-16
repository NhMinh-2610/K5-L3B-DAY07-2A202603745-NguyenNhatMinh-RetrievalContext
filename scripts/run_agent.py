"""Chạy agent DeepSeek trên dev; không mở bộ test hoặc tự chấm đúng sai."""
import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from prepare_day6 import read_json, require, sha256
from src.agent import SYSTEM_PROMPT, run_agent
from src.day6_connection import Day6Connection
from src.deepseek_client import DeepSeekClient, load_api_key, validate_config
from src.retrieval import validate_query
from src.retriever_service import RetrieverService


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_dev(source):
    definition = read_json(ROOT / "benchmark/split.json")
    for name, expected in definition["files_sha256"].items():
        require(sha256(ROOT / "benchmark" / name) == expected, f"Benchmark đã thay đổi: {name}")
    chunks_path = ROOT / "starter/data/day6/chunks.json"
    require(sha256(chunks_path) == definition["chunks_sha256"], "Chunk khác bản benchmark đã chốt.")
    source_config = read_json(source / "starter/strategies.json")
    require(sha256(source / source_config["corpus_path"]) == definition["corpus_sha256"], "Corpus nguồn đã thay đổi.")
    with (ROOT / "benchmark/review.csv").open(encoding="utf-8-sig", newline="") as stream:
        reviews = list(csv.DictReader(stream))
    require(len(reviews) == 24 and all(row["status"] == "confirmed" for row in reviews), "Cần xác nhận nguồn benchmark.")
    queries = read_json(ROOT / "benchmark/dev_queries.json")
    require([row["id"] for row in queries] == definition["dev_ids"], "Danh sách query không khớp dev.")
    for query in queries:
        validate_query(query)
        require(query["split"] == "dev", "Chỉ chạy dev trước khi chốt cấu hình.")
    return definition, queries, read_json(chunks_path), read_json(ROOT / "starter/data/day6/manifest.json")


def prepare_reviews(traces):
    # Chỉ đọc nhãn dev sau khi agent đã trả lời xong các câu được chọn.
    cases = {case["id"]: case for case in read_json(ROOT / "benchmark/dev.json")}
    checks = {case["query_id"]: case for case in read_json(ROOT / "benchmark/dev_source_checks.json")}
    reviews, context_n, context_N = [], 0, 0
    for trace in traces:
        case = cases[trace["query_id"]]
        if trace["status"] == "error":
            continue
        review = {"query_id": trace["query_id"], "status": "pending", "context_grade": None,
                  "citation_support": [None] * len(trace["citations"]), "reason": ""}
        if case["answerable"]:
            review["answer_grade"] = None
            context_N += 1
            ids = set(trace["context_ids"])
            context_n += any(set(item["supporting_chunk_ids"]) <= ids
                             and bool(item["supporting_chunk_ids"]) for item in checks[case["id"]]["evidence"])
        else:
            review["abstention_correct"] = None
        reviews.append(review)
    return reviews, {"n": context_n, "N": context_N,
                     "rate": context_n / context_N if context_N else None,
                     "scope": "Context thực gửi model; đối chiếu tự động theo các chunk phủ evidence, chưa chấm ngữ nghĩa."}


def run(source, config_path, env_path, selected_ids, all_dev, output):
    config = read_json(config_path)
    validate_config(config)
    api_key = load_api_key(env_path)
    definition, queries, chunks, imported = load_dev(source)
    if not all_dev:
        require(bool(selected_ids) and len(selected_ids) == len(set(selected_ids)), "Chọn ID dev khác nhau.")
        require(set(selected_ids) <= set(definition["dev_ids"]), "ID không thuộc dev; không chạy test ở bước này.")
        queries = [query for query in queries if query["id"] in selected_ids]
    output.mkdir(parents=True, exist_ok=True)
    save(output / "summary.json", {"status": "running", "split": "dev", "requested_queries": len(queries)})
    connection, client = None, None
    try:
        client = DeepSeekClient(config, api_key)
        connection = Day6Connection(source, chunks, imported)
        retriever = RetrieverService(connection, chunks, read_json(ROOT / "config/retrieval.json"))
        traces = []
        with (output / "traces.jsonl").open("w", encoding="utf-8") as stream:
            for query in queries:
                before_requests = client.api_requests
                trace = run_agent(query, client, retriever, config)
                trace["api_requests"] = client.api_requests - before_requests
                traces.append(trace)
                stream.write(json.dumps(trace, ensure_ascii=False) + "\n")
                stream.flush()
                print(f"{query['id']}: {trace['status']}, search={trace['search_count']}, API={trace['api_requests']}", flush=True)
                if trace["status"] == "answered":
                    print(trace["answer"], flush=True)
                elif trace["status"] == "error":
                    print(trace["error"], flush=True)
                if trace.get("error_type") in ("ProviderCallError", "CostLimitError"):
                    break
        save(output / "traces.json", traces)
        review_path = output / "reviews_template.json"
        reviews, context_metric = prepare_reviews(traces)
        save(review_path, reviews)
        statuses = dict(Counter(trace["status"] for trace in traces))
        successful = [trace for trace in traces if trace["status"] != "error"]
        responses = [event["response"] for trace in traces for event in trace["events"]
                     if event.get("event") == "model_call" and "response" in event]
        token_usage = {key: sum(response["usage"].get(key, 0) for response in responses)
                       for key in ("prompt_tokens", "completion_tokens", "total_tokens")}
        complete = len(traces) == len(queries)
        summary = {
            "status": "complete" if complete and "error" not in statuses else "complete_with_errors" if complete else "partial",
            "split": "dev", "completed_at_utc": datetime.now(timezone.utc).isoformat(),
            "config": config, "config_sha256": sha256(config_path),
            "system_prompt_sha256": hashlib.sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest(),
            "agent_code_sha256": sha256(ROOT / "src/agent.py"),
            "corpus_sha256": definition["corpus_sha256"], "dev_sha256": definition["files_sha256"]["dev.json"],
            "requested_query_ids": [query["id"] for query in queries], "processed_queries": len(traces),
            "statuses": statuses, "api_requests": client.api_requests,
            "usage_from_successful_responses": {"response_count": len(responses), **token_usage},
            "returned_models": sorted({response["model"] for response in responses}),
            "system_fingerprints": sorted({response["system_fingerprint"] for response in responses
                                            if response.get("system_fingerprint")}),
            "estimated_cost_upper_usd": client.estimated_cost_upper_usd,
            "cost_is_invoice": False, "provenance": connection.provenance,
            "tool_use": {"n": sum(trace["search_count"] > 0 for trace in successful), "N": len(successful)},
            "search_count_distribution": dict(Counter(trace["search_count"] for trace in successful)),
            "context_evidence": context_metric, "semantic_reviews_pending": len(reviews),
            "test_evaluated": False, "configuration_selected": False,
            "limitations": [
                "Citation ID có trong context chưa chứng minh nguồn hỗ trợ mọi khẳng định.",
                "Chưa chấm đúng sai câu trả lời, citation hoặc từ chối; reviews_template.json cần nhãn đã kiểm tra.",
                "Chi phí ước tính theo usage và giá giờ cao điểm đã lưu; không phải hóa đơn thực tế.",
                "Request thất bại được dự phòng chi phí bảo thủ; không tự retry API.",
            ],
        }
        save(output / "summary.json", summary)
        return summary
    finally:
        if connection is not None:
            connection.close()
        if client is not None:
            client.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--day6", type=Path)
    parser.add_argument("--config", type=Path, default=ROOT / "config/agent.json")
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--check-config", action="store_true", help="Chỉ kiểm tra cấu hình, không gọi API/database")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--all-dev", action="store_true")
    mode.add_argument("--query-id", nargs="+")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.check_config:
        try:
            config = read_json(args.config)
            validate_config(config)
            load_api_key(args.env_file)
            print("Cấu hình hợp lệ; DEEPSEEK_API_KEY đã có. Chưa gọi API hoặc database.")
        except ValueError as error:
            parser.exit(1, str(error) + "\n")
        return
    if not args.day6 or not (args.all_dev or args.query_id):
        parser.error("Cần --day6 và chọn --all-dev hoặc --query-id; dùng --check-config để kiểm tra key.")
    output = (args.output or ROOT / "results/agent" / ("dev-baseline" if args.all_dev else "dev-smoke")).resolve()
    require(output.is_relative_to(ROOT), "Thư mục kết quả phải nằm trong repo Day 7.")
    try:
        summary = run(args.day6.resolve(), args.config.resolve(), args.env_file.resolve(),
                      args.query_id, args.all_dev, output)
    except Exception as error:
        if output.exists():
            save(output / "summary.json", {"status": "failed", "split": "dev", "error_type": type(error).__name__, "error": str(error)})
        parser.exit(1, f"Chưa hoàn tất agent dev: {error}\n")
    print(f"Kết quả: {output.relative_to(ROOT)}")
    print(f"Trạng thái: {summary['status']}; chi phí ước tính theo giá cao điểm: ${summary['estimated_cost_upper_usd']:.6f}")
    if summary["status"] != "complete":
        parser.exit(1)


if __name__ == "__main__":
    main()
