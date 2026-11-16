"""Thử nghiệm dev, chốt cấu hình và đánh giá test với hàng rào chống dùng test để chỉnh."""
import argparse
import copy
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from prepare_day6 import read_json, require, sha256
from run_agent import load_dev, save
from src.agent import run_agent
from src.day6_connection import Day6Connection
from src.deepseek_client import DeepSeekClient, load_api_key
from src.evaluation import aggregate, grade_trace
from src.retriever_service import RetrieverService

CORE = ("src/agent.py", "src/retrieval.py", "src/retriever_service.py", "src/day6_connection.py",
        "src/deepseek_client.py", "src/evaluation.py")
STUDY = ROOT / "results/study"


def fingerprints():
    return {name: sha256(ROOT / name) for name in CORE}


class LockedConnection:
    def __init__(self, connection):
        self.connection = connection
        self.lock = threading.Lock()

    def embed_query(self, query):
        with self.lock:
            return self.connection.embed_query(query)

    def search_vector(self, vector, **kwargs):
        with self.lock:
            return self.connection.search_vector(vector, **kwargs)


def run_configuration(identifier, config_path, split, queries, chunks, connection, key):
    output = STUDY / split / identifier
    output.mkdir(parents=True, exist_ok=True)
    config = read_json(config_path)
    config_hash = sha256(config_path)
    code_hashes = fingerprints()
    trace_path = output / "traces.json"
    cached = []
    if trace_path.exists():
        metadata = read_json(output / "run.json")
        require(metadata["config_sha256"] == config_hash and metadata["core_sha256"] == code_hashes,
                "Thư mục đã có kết quả của phiên bản khác; cần thư mục thí nghiệm mới.")
        cached = read_json(trace_path)
    else:
        save(output / "run.json", {"config_sha256": config_hash, "core_sha256": code_hashes,
                                  "started_at_utc": datetime.now(timezone.utc).isoformat(), "split": split,
                                  "query_ids": [row["id"] for row in queries]})
    by_id = {row["query_id"]: row for row in cached}
    generator = DeepSeekClient(config, key)
    judge_config = {**config, "max_output_tokens": 1500}
    judge = DeepSeekClient(judge_config, key)
    retriever = RetrieverService(connection, chunks, read_json(ROOT / "config/retrieval.json"))
    try:
        for query in queries:
            if query["id"] in by_id:
                continue
            before = generator.api_requests
            trace = run_agent(query, generator, retriever, config)
            trace["api_requests"] = generator.api_requests - before
            by_id[query["id"]] = trace
            save(trace_path, [by_id[row["id"]] for row in queries if row["id"] in by_id])
            print(f"{split}/{identifier}/{query['id']}: {trace['status']}", flush=True)
            if trace.get("error_type") in ("ProviderCallError", "CostLimitError"):
                raise RuntimeError(trace["error"])
        traces = [by_id[row["id"]] for row in queries]
        # Nhãn của split chỉ được đọc sau khi đã chạy hết query của cấu hình đó.
        cases = read_json(ROOT / f"benchmark/{split}.json")
        case_by_id = {row["id"]: row for row in cases}
        reviews_path = output / "reviews.json"
        reviews = read_json(reviews_path) if reviews_path.exists() else []
        review_by_id = {row["query_id"]: row for row in reviews}
        chunk_by_id = {row["id"]: row for row in chunks}
        for trace in traces:
            if trace["status"] == "error" or trace["query_id"] in review_by_id:
                continue
            review = grade_trace(judge, case_by_id[trace["query_id"]], trace, chunk_by_id)
            review_by_id[trace["query_id"]] = review
            save(reviews_path, list(review_by_id.values()))
            print(f"{split}/{identifier}/{trace['query_id']}: graded", flush=True)
        reviews = list(review_by_id.values())
        metrics = aggregate(cases, traces, reviews, read_json(ROOT / f"benchmark/{split}_source_checks.json"))
        responses = [event["response"] for trace in traces for event in trace["events"]
                     if event["event"] == "model_call" and "response" in event]
        generation_cost = sum(response["estimated_cost_upper_usd"] for response in responses)
        judge_cost = sum(review["judge_response"]["estimated_cost_upper_usd"] for review in reviews)
        summary = {"status": "complete", "split": split, "configuration": identifier, "config": config,
                   "config_sha256": config_hash, "core_sha256": code_hashes, "metrics": metrics,
                   "generation_cost_upper_usd": generation_cost, "judge_cost_upper_usd": judge_cost,
                   "total_cost_upper_usd": generation_cost + judge_cost,
                   "api_requests": sum(trace["api_requests"] for trace in traces) + len(reviews),
                   "generation_usage": {name: sum(response["usage"].get(name, 0) for response in responses)
                                        for name in ("prompt_tokens", "completion_tokens", "total_tokens")},
                   "judge_usage": {name: sum(review["judge_response"]["usage"].get(name, 0) for review in reviews)
                                   for name in ("prompt_tokens", "completion_tokens", "total_tokens")},
                   "completed_at_utc": datetime.now(timezone.utc).isoformat(),
                   "cost_is_invoice": False, "semantic_labels": "model_proposed"}
        save(output / "summary.json", summary)
        return summary
    finally:
        generator.close()
        judge.close()


def selection_key(summary):
    metrics = summary["metrics"]
    rate = lambda name: metrics[name]["rate"] or 0
    return (metrics["errors"], -metrics["answer_score_over_expected"],
            -rate("abstention"), rate("false_abstention"), -rate("citation_validity"),
            -rate("context_semantic"), summary["total_cost_upper_usd"], metrics["median_seconds"])


def execute(source, phase):
    plan_path = ROOT / "config/experiment_plan.json"
    plan = read_json(plan_path)
    definition, dev_queries, chunks, imported = load_dev(source)
    if phase == "test":
        selection = read_json(STUDY / "selection.json")
        require(selection["status"] == "fixed" and selection["core_sha256"] == fingerprints(), "Code đã thay đổi sau khi chốt.")
        require(selection["plan_sha256"] == sha256(plan_path), "Kế hoạch đã thay đổi sau khi chốt.")
        require(selection["benchmark_sha256"] == sha256(ROOT / "benchmark/split.json"), "Benchmark đã thay đổi.")
        for name, digest in selection["config_sha256"].items():
            require(sha256(ROOT / name) == digest, "Cấu hình đã thay đổi sau khi chốt.")
        for name, digest in selection["dev_summaries_sha256"].items():
            require(sha256(ROOT / name) == digest, "Kết quả dev đã thay đổi sau khi chốt.")
        identifiers = list(dict.fromkeys(["baseline", selection["selected_configuration"]]))
        queries = read_json(ROOT / "benchmark/test_queries.json")
        require([row["id"] for row in queries] == definition["test_ids"], "Sai tập test.")
    else:
        require(not (STUDY / "test").exists(), "Đã có kết quả test; không chỉnh hoặc chọn lại trên dev.")
        identifiers = [row["id"] for row in plan["configurations"]]
        queries = dev_queries
    configs = {row["id"]: ROOT / row["path"] for row in plan["configurations"]}
    api_key = load_api_key(ROOT / ".env")
    connection = Day6Connection(source, chunks, imported)
    try:
        shared = LockedConnection(connection)
        with ThreadPoolExecutor(max_workers=3) as executor:
            jobs = [executor.submit(run_configuration, identifier, configs[identifier], phase,
                                    queries, chunks, shared, api_key) for identifier in identifiers]
            summaries = [job.result() for job in jobs]
        STUDY.mkdir(parents=True, exist_ok=True)
        save(STUDY / f"{phase}_comparison.json", summaries)
        save(STUDY / "data_provenance.json", connection.provenance)
        if phase == "dev":
            best = min(summaries, key=selection_key)
            selection = {
                "status": "fixed", "selected_configuration": best["configuration"],
                "fixed_at_utc": datetime.now(timezone.utc).isoformat(),
                "selection_criteria": plan["selection_criteria"], "core_sha256": fingerprints(),
                "plan_sha256": sha256(plan_path), "benchmark_sha256": sha256(ROOT / "benchmark/split.json"),
                "config_sha256": {str(path.relative_to(ROOT)).replace("\\", "/"): sha256(path) for path in configs.values()},
                "dev_summaries_sha256": {str((STUDY / "dev" / identifier / "summary.json").relative_to(ROOT)).replace("\\", "/"):
                                         sha256(STUDY / "dev" / identifier / "summary.json") for identifier in identifiers},
                "test_used_for_selection": False, "label_origin": "model_proposed",
            }
            save(STUDY / "selection.json", selection)
        print(json.dumps({"phase": phase, "configurations": identifiers,
                          "selected": read_json(STUDY / "selection.json")["selected_configuration"]}, ensure_ascii=False), flush=True)
    finally:
        connection.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--day6", type=Path, required=True)
    parser.add_argument("--phase", choices=("dev", "test"), required=True)
    args = parser.parse_args()
    execute(args.day6.resolve(), args.phase)


if __name__ == "__main__":
    main()
