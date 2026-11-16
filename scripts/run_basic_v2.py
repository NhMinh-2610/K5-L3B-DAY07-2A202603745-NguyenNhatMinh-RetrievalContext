"""Thí nghiệm mới cho context lân cận; giữ nguyên lần nghiên cứu/test cũ."""
import argparse
import copy
import hashlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from complete_lab import CORE, LockedConnection
from src.agent import run_agent
from src.context_retriever import NeighborRetriever
from src.day6_connection import Day6Connection
from src.deepseek_client import DeepSeekClient, load_api_key
from src.evaluation import aggregate, grade_trace
from src.retrieval_metrics import evidence_hit
from src.retriever_service import RetrieverService

OUT = ROOT / "results/extension/basic-v2"
BENCH = ROOT / "benchmark/basic-v2"


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")


def hashes():
    names = [*CORE, "src/context_retriever.py", "scripts/run_basic_v2.py", "config/basic-v2.json",
             "benchmark/dev.json", "benchmark/dev_queries.json", "benchmark/basic-v2/test.json",
             "benchmark/basic-v2/test_queries.json", "starter/data/day6/chunks.json"]
    return {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in names}


def source_checks(cases, chunks):
    normalize = lambda text: " ".join(text.split())
    checks = []
    for case in cases:
        evidence = []
        for gold in case.get("gold", []):
            rows = sorted([c for c in chunks if c["source_id"]==gold["source_id"] and c["page"]==gold["page"]],
                          key=lambda c:c["metadata"].get("page_char_start", 0))
            text, offsets = "", []
            for row in rows:
                start = len(text)
                text += (" " if text else "")+normalize(row["text"])
                offsets.append((start,len(text),row["id"]))
            needle = normalize(gold["evidence"])
            start = text.find(needle)
            assert start >= 0, "Gold không khớp corpus: "+case["id"]
            ids = [cid for a,b,cid in offsets if a < start+len(needle) and b > start]
            evidence.append({"supporting_chunk_ids":ids})
        checks.append({"query_id":case["id"],"evidence":evidence})
    return checks


def execute_config(name, spec, phase, queries, connection, original):
    folder = OUT/phase/name
    base = RetrieverService(connection, original, read(ROOT/"config/retrieval.json"))
    service = NeighborRetriever(base, original, spec["radius"]) if spec["radius"] else base
    chunks = service.chunks if spec["radius"] else original
    config = {**read(ROOT/"config/agent.json"), **spec["agent"]}
    trace_path = folder/"traces.json"
    if trace_path.exists():
        assert read(folder/"run.json")["sha256"]==hashes(), "Không dùng cache khác phiên bản."
        traces = read(trace_path)
    else:
        save(folder/"run.json", {"sha256":hashes(), "started_at_utc":datetime.now(timezone.utc).isoformat()})
        traces = []
    generator = DeepSeekClient(config, load_api_key(ROOT/".env"))
    judge = DeepSeekClient({**config,"max_output_tokens":1500},load_api_key(ROOT/".env"))
    try:
        done = {row["query_id"] for row in traces}
        for query in queries:
            if query["id"] in done:
                continue
            before = generator.api_requests
            trace = run_agent(query,generator,service,config)
            trace["api_requests"] = generator.api_requests-before
            traces.append(trace);save(trace_path,traces)
            print(f"{phase}/{name}/{query['id']}: {trace['status']}",flush=True)
            if trace.get("error_type") in ("ProviderCallError","CostLimitError"):
                raise RuntimeError(trace["error"])
        # Gold chỉ được đọc để chấm sau khi đã hoàn tất sinh đáp án của split.
        cases = read(ROOT/"benchmark/dev.json" if phase=="dev" else BENCH/"test.json")
        by_case = {row["id"]:row for row in cases}
        lookup = {row["id"]:row for row in chunks}
        reviews = read(folder/"reviews.json") if (folder/"reviews.json").exists() else []
        graded = {row["query_id"] for row in reviews}
        for trace in traces:
            if trace["status"]!="error" and trace["query_id"] not in graded:
                reviews.append(grade_trace(judge,by_case[trace["query_id"]],trace,lookup))
                save(folder/"reviews.json",reviews)
        metric_traces = copy.deepcopy(traces)
        for trace in metric_traces:
            trace["context_ids"] = list(dict.fromkeys(cid for i in trace["context_ids"]
                        for cid in lookup[i]["metadata"].get("source_chunk_ids",[i])))
        metrics = aggregate(cases,metric_traces,reviews,source_checks(cases,original))
        metrics["ranking_scope"] = "Evidence group nếu có mở rộng; ranking seed gốc được lưu riêng trong trace."
        positives = [t for t in traces if by_case[t["query_id"]]["answerable"] and t["status"]!="error"]
        for cutoff in (1,3):
            hit = 0
            for trace in positives:
                search = next(e for e in trace["events"] if e["event"]=="search")
                seeds = search["retrieval"].get("seed_results",search["results"])
                hit += any(evidence_hit(c,by_case[trace["query_id"]]["gold"]) for c in seeds[:cutoff])
            metrics[f"seed_hit{cutoff}"] = {"n":hit,"N":len(positives),"rate":hit/len(positives)}
        model_cost = sum(e["response"]["estimated_cost_upper_usd"] for t in traces for e in t["events"] if "response" in e)
        judge_cost = sum(r["judge_response"]["estimated_cost_upper_usd"] for r in reviews)
        result = {"configuration":name,"config":config,"metrics":metrics,"generation_cost_upper_usd":model_cost,
                  "judge_cost_upper_usd":judge_cost,"total_cost_upper_usd":model_cost+judge_cost,
                  "label_origin":"model_proposed", "completed_at_utc":datetime.now(timezone.utc).isoformat()}
        save(folder/"summary.json",result)
        if spec["radius"]:
            save(folder/"evidence_groups.json", [{k:c[k] for k in ("id","source_id","source","page","metadata")} for c in chunks])
        return result
    finally:
        generator.close();judge.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--day6",required=True,type=Path)
    parser.add_argument("--phase",choices=("dev","test"),required=True)
    args = parser.parse_args()
    plan = read(ROOT/"config/basic-v2.json")
    if args.phase=="test":
        selection = read(OUT/"selection.json")
        assert selection["sha256"]==hashes(), "Phiên bản khác lúc chốt."
        names = list(dict.fromkeys(["baseline",selection["selected_configuration"]]))
        queries = read(BENCH/"test_queries.json")
    else:
        assert not (OUT/"test").exists(), "Đã có test, không chọn lại."
        names = list(plan["configurations"])
        queries = read(ROOT/"benchmark/dev_queries.json")
    chunks = read(ROOT/"starter/data/day6/chunks.json")
    connection = Day6Connection(args.day6.resolve(),chunks,read(ROOT/"starter/data/day6/manifest.json"))
    try:
        shared = LockedConnection(connection)
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = [pool.submit(execute_config,name,plan["configurations"][name],args.phase,queries,shared,chunks) for name in names]
            summaries = [future.result() for future in futures]
        save(OUT/f"{args.phase}_comparison.json",summaries)
        if args.phase=="dev":
            selected = min(summaries,key=lambda s:(s["metrics"]["errors"],-s["metrics"]["answer_score_over_expected"],
                            -(s["metrics"]["citation_validity"]["rate"] or 0),s["total_cost_upper_usd"]))
            save(OUT/"selection.json", {"selected_configuration":selected["configuration"],"sha256":hashes(),
                 "fixed_at_utc":datetime.now(timezone.utc).isoformat(),"test_used_for_selection":False})
    finally:
        connection.close()


if __name__=="__main__":
    main()
