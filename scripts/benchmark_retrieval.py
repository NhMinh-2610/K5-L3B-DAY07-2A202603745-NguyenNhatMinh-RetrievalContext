"""So sánh dense, TF-IDF và hybrid trên dev; chưa chạy agent hoặc test."""
import argparse
import csv
import json
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from prepare_day6 import read_json, require, sha256
from src.day6_connection import Day6Connection
from src.retrieval import LexicalRetriever, pack_context, reciprocal_rank_fusion, validate_query
from src.retrieval_metrics import evaluate_trace, summarize


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def validate_config(config):
    require(len(config["methods"]) == 3 and set(config["methods"]) == {"dense", "tfidf", "hybrid"},
            "Cần ba phương pháp dense, tfidf, hybrid, không trùng tên.")
    for key in ("top_k", "context_budget_chars", "hybrid_candidate_k", "rrf_constant"):
        require(type(config[key]) is int and config[key] > 0, f"{key} phải là số nguyên dương.")
    require(config["top_k"] >= 3 and config["hybrid_candidate_k"] >= config["top_k"],
            "Cần xuất ít nhất top-3; số candidate hybrid không nhỏ hơn top_k.")
    require(config.get("filter_policy") == "query_provided_only", "Filter chỉ được lấy từ query.")


def run(source, config_path, output):
    config = read_json(config_path)
    validate_config(config)
    definition = read_json(ROOT / "benchmark/split.json")
    for name, expected in definition["files_sha256"].items():
        require(sha256(ROOT / "benchmark" / name) == expected,
                f"Dữ liệu khác benchmark đã chốt: {name}")
    chunks_path = ROOT / "starter/data/day6/chunks.json"
    require(sha256(chunks_path) == definition["chunks_sha256"], "Chunk khác bản benchmark đã chốt.")
    source_config = read_json(source / "starter/strategies.json")
    require(sha256(source / source_config["corpus_path"]) == definition["corpus_sha256"],
            "Corpus nguồn đã thay đổi.")
    with (ROOT / "benchmark/review.csv").open(encoding="utf-8-sig", newline="") as stream:
        reviews = list(csv.DictReader(stream))
    all_ids = set(definition["dev_ids"] + definition["test_ids"])
    require(len(reviews) == len(all_ids) and {row["id"] for row in reviews} == all_ids
            and all(row["status"] == "confirmed" for row in reviews), "Cần xác nhận đủ nguồn trước khi chạy.")
    queries = read_json(ROOT / "benchmark/dev_queries.json")
    require([q["id"] for q in queries] == definition["dev_ids"], "Đầu vào không đúng bộ dev.")
    for query in queries:
        validate_query(query)
        require(query["split"] == "dev", "Lệnh này chỉ chạy dev.")

    chunks = read_json(chunks_path)
    imported = read_json(ROOT / "starter/data/day6/manifest.json")
    started = time.perf_counter()
    lexical = LexicalRetriever(chunks)
    lexical_build_seconds = time.perf_counter() - started
    connection = Day6Connection(source, chunks, imported)
    traces = []
    try:
        with (output / "traces.jsonl").open("w", encoding="utf-8") as stream:
            for query in queries:
                embedding_started = time.perf_counter()
                vector = connection.embed_query(query["question"])
                embedding_ms = (time.perf_counter() - embedding_started) * 1000
                for method in config["methods"]:
                    events = []

                    def search(tool, count):
                        search_started = time.perf_counter()
                        if tool == "dense":
                            result = connection.search_vector(vector, filters=query["filter"], top_k=count)
                        else:
                            result = lexical.search(query["question"], filters=query["filter"], top_k=count)
                        events.append({"event": "search", "tool": tool, "query": query["question"],
                                       "filter": query["filter"], "top_k": count, "results": result,
                                       "elapsed_ms": (time.perf_counter() - search_started) * 1000})
                        return result

                    retrieval_started = time.perf_counter()
                    if method == "hybrid":
                        dense = search("dense", config["hybrid_candidate_k"])
                        tfidf = search("tfidf", config["hybrid_candidate_k"])
                        results = reciprocal_rank_fusion({"dense": dense, "tfidf": tfidf},
                                                         constant=config["rrf_constant"], top_k=config["top_k"])
                    else:
                        results = search(method, config["top_k"])
                    retrieval_ms = (time.perf_counter() - retrieval_started) * 1000
                    context, context_ids = pack_context(results, budget_chars=config["context_budget_chars"])
                    trace = {"query_id": query["id"], "split": "dev", "question": query["question"],
                             "method": method, "status": "retrieved", "filter": query["filter"],
                             "top_k": config["top_k"], "events": events,
                             "results": [{**row, "rank": rank} for rank, row in enumerate(results, 1)],
                             "context": context, "context_ids": context_ids,
                             "context_budget_chars": config["context_budget_chars"],
                             "retrieval_ms": retrieval_ms,
                             "query_embedding_ms_shared": embedding_ms if method != "tfidf" else 0.0}
                    traces.append(trace)
                    stream.write(json.dumps(trace, ensure_ascii=False) + "\n")
                    stream.flush()
                print(f"Đã truy xuất {query['id']}: dense / tfidf / hybrid", flush=True)

        # Chỉ đọc nhãn dev sau khi truy xuất xong toàn bộ query.
        cases = {case["id"]: case for case in read_json(ROOT / "benchmark/dev.json")}
        checks = {case["query_id"]: case for case in read_json(ROOT / "benchmark/dev_source_checks.json")}
        for query in queries:
            require(query["question"] == cases[query["id"]]["question"]
                    and query["filter"] == cases[query["id"]]["filter"], "Query khác nhãn dev.")
        evaluated = [evaluate_trace(trace, cases[trace["query_id"]], checks[trace["query_id"]]) for trace in traces]
        save(output / "evaluated_dev.json", evaluated)
        metrics = summarize(evaluated, config["methods"])
        summary = {
            "status": "complete", "split": "dev", "completed_at_utc": datetime.now(timezone.utc).isoformat(),
            "python": platform.python_version(), "config": config,
            "config_sha256": sha256(config_path), "corpus_sha256": definition["corpus_sha256"],
            "chunks_sha256": definition["chunks_sha256"], "dev_sha256": definition["files_sha256"]["dev.json"],
            "provenance": connection.provenance, "lexical_index_build_seconds": lexical_build_seconds,
            "trace_rows": len(traces), "query_count": len(queries), "metrics": metrics,
            "source_review_confirmed": len(reviews), "test_evaluated": False,
            "agent_evaluated": False, "configuration_selected": False, "paid_api_calls": 0,
            "limitations": [
                "Context được chuẩn bị từ retrieval, chưa gửi model; chưa phải Context Evidence Rate của agent.",
                "Chưa chấm câu trả lời, citation hoặc khả năng từ chối của agent.",
                "Embedding query được tính một lần mỗi câu và dùng chung cho dense/hybrid; ghi thời gian riêng.",
                "Thời gian là một lần chạy tuần tự, có ảnh hưởng của cache; model load được báo riêng.",
                "TF-IDF tách từ đơn giản, không dịch câu hỏi tiếng Việt sang tài liệu tiếng Anh.",
                "Phí dịch vụ 0 USD chưa tính điện và phần cứng.",
            ],
        }
        save(output / "summary.json", summary)
        with (output / "metrics.csv").open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(metrics[0]))
            writer.writeheader()
            writer.writerows(metrics)
        return summary
    finally:
        connection.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--day6", required=True, type=Path)
    parser.add_argument("--config", type=Path, default=ROOT / "config/retrieval.json")
    parser.add_argument("--output", type=Path, default=ROOT / "results/retrieval/dev")
    args = parser.parse_args()
    output = args.output.resolve()
    require(output.is_relative_to(ROOT), "Thư mục kết quả phải nằm trong repo Day 7.")
    output.mkdir(parents=True, exist_ok=True)
    save(output / "summary.json", {"status": "running", "split": "dev"})
    try:
        result = run(args.day6.resolve(), args.config.resolve(), output)
    except Exception as error:
        save(output / "summary.json", {"status": "failed", "split": "dev",
                                       "error_type": type(error).__name__, "error": str(error)})
        parser.exit(1, f"Không hoàn tất truy xuất dev: {error}\n")
    for row in result["metrics"]:
        print(f"{row['method']}: Hit@1 {row['hit1_n']}/{row['answerable_n']}; "
              f"Evidence Hit@3 {row['evidence_hit3_n']}/{row['answerable_n']}")


if __name__ == "__main__":
    main()
