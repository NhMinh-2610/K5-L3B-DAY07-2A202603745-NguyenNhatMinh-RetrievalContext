"""Chạy/chấm dev và test bonus; giữ mọi câu trong mẫu số, ghi nguồn gốc nhãn."""
import argparse
import hashlib
import json
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from complete_lab import CORE
from src.advanced_agent import run_agent
from src.vision_client import VisionClient
from src.deepseek_client import DeepSeekClient,load_api_key
from src.document_store import DocumentStore,DocumentRetriever
from src.evaluation import grade_trace

OUT=ROOT/"results/extension/advanced-v2"
BENCH=ROOT/"benchmark/advanced"


def read(path):return json.loads(path.read_text(encoding="utf-8-sig"))


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")


def hashes():
    files=[*CORE,"src/document_store.py","src/advanced_agent.py","src/vision_client.py","scripts/run_advanced.py","scripts/prepare_advanced.py",
           "config/advanced.json","advanced/visual_readings.json","starter/data/advanced/chunks.json",
           "starter/data/advanced/vectors.json",*[str(p.relative_to(ROOT)).replace('\\','/') for p in BENCH.glob("*.json")]]
    return {name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in files}


def pass_result(case,trace,review,lookup):
    if trace["status"]=="error" or not review:return False
    if not case["answerable"]:
        return trace["status"]=="abstain" and review["abstention_correct"] and trace["search_count"]>0
    cited=[lookup[i] for i in trace["citations"]]
    coverage=all(any(c["page"]==gold["page"] and (not gold["reference"] or c["metadata"].get("reference")==gold["reference"]) for c in cited) for gold in case["gold"])
    return (trace["status"]=="answered" and review["answer_grade"]==2 and bool(cited)
            and all(review["citation_support"]) and coverage)


class JudgeRecorder:
    def __init__(self,client,attempts,path):self.client=client;self.attempts=attempts;self.path=path;self.retry=False
    def complete(self,messages,tools,tool_choice):
        if self.retry:messages=[*messages,{"role":"system","content":"Chỉ trả function call JSON hợp lệ; escape dấu ngoặc kép trong chuỗi, không cắt thiếu dấu đóng."}]
        response=self.client.complete(messages,tools,tool_choice)
        self.attempts.append({"request":messages,"response":response})
        save(self.path,self.attempts)
        return response


def execute(name,spec,phase,queries,store):
    folder=OUT/phase/name;fingerprint=hashes()
    config={**read(ROOT/"config/agent.json"),**spec["agent"],"max_output_tokens":1200}
    trace_path=folder/"traces.json"
    if trace_path.exists():
        assert read(folder/"run.json")["sha256"]==fingerprint,"Không dùng cache khác phiên bản."
        traces=read(trace_path)
    else:
        save(folder/"run.json",{"sha256":fingerprint,"started_at_utc":datetime.now(timezone.utc).isoformat()})
        traces=[]
    key=load_api_key(ROOT/".env")
    generator=(VisionClient(config,key,store.chunks,ROOT/"starter/data/advanced") if spec["vision"] else DeepSeekClient(config,key))
    judge_client=DeepSeekClient({**config,"max_output_tokens":2000},key)
    retriever=DocumentRetriever(store,anchored=spec["anchors"])
    try:
        done={row["query_id"] for row in traces}
        for query in queries:
            if query["id"] in done:continue
            before=generator.api_requests
            trace=run_agent(query,generator,retriever.for_question(query["question"]),config)
            trace["api_requests"]=generator.api_requests-before
            traces.append(trace);save(trace_path,traces)
            print(f"{phase}/{name}/{query['id']}: {trace['status']}",flush=True)
            if trace.get("error_type") in ("ProviderCallError","CostLimitError"):raise RuntimeError(trace["error"])
        # Bộ gold chỉ được đọc sau khi đã hoàn tất sinh đáp án của split.
        cases=read(BENCH/f"{phase}.json");by_case={c["id"]:c for c in cases}
        lookup={c["id"]:c for c in store.chunks}
        reviews=read(folder/"reviews.json") if (folder/"reviews.json").exists() else []
        attempts=read(folder/"grading_attempts.json") if (folder/"grading_attempts.json").exists() else []
        recorder=JudgeRecorder(judge_client,attempts,folder/"grading_attempts.json")
        reviewed={r["query_id"] for r in reviews}
        for trace in traces:
            if trace["status"]=="error" or trace["query_id"] in reviewed:continue
            for attempt in range(3):
                recorder.retry=attempt>0
                try:
                    review=grade_trace(recorder,by_case[trace["query_id"]],trace,lookup)
                    reviews.append(review);save(folder/"reviews.json",reviews)
                    print(f"{phase}/{name}/{trace['query_id']}: graded",flush=True)
                    break
                except (ValueError,KeyError) as error:
                    save(folder/"grading_incidents.json",{"query_id":trace["query_id"],"attempt":attempt+1,"error_type":type(error).__name__,"generation_rerun":False})
                    if attempt==2:raise
        by_trace={t["query_id"]:t for t in traces};by_review={r["query_id"]:r for r in reviews}
        labels=[]
        for case in cases:
            trace=by_trace[case["id"]];review=by_review.get(case["id"])
            labels.append({"query_id":case["id"],"group":case["group"],"passed":pass_result(case,trace,review,lookup),
                           "status":trace["status"],"review_status":"model_proposed",
                           "reason":review["answer_reason"] if review and case["answerable"] else (review["abstention_reason"] if review else trace.get("error","Không có nhãn"))})
        save(folder/"binary_labels.json",labels)
        groups={}
        for group in sorted({c["group"] for c in cases}):
            rows=[r for r in labels if r["group"]==group];n=sum(r["passed"] for r in rows)
            groups[group]={"n":n,"N":len(rows),"rate":n/len(rows)}
        generation_cost=sum(e["response"]["estimated_cost_upper_usd"] for t in traces for e in t["events"] if "response" in e)
        grading_cost=sum(a["response"]["estimated_cost_upper_usd"] for a in attempts)
        passed=sum(row["passed"] for row in labels)
        result={"configuration":name,"config":config,"passed":passed,"total":len(cases),"rate":passed/len(cases),
                "by_group":groups,"errors":sum(t["status"]=="error" for t in traces),
                "statuses":dict(Counter(t["status"] for t in traces)),"generation_cost_upper_usd":generation_cost,
                "judge_cost_upper_usd":grading_cost,"total_cost_upper_usd":generation_cost+grading_cost,
                "api_requests":sum(t["api_requests"] for t in traces)+len(attempts),
                "label_origin":"model_proposed; yêu cầu đối chiếu bản gốc từng câu trước khi xác nhận bonus",
                "completed_at_utc":datetime.now(timezone.utc).isoformat(),"all_test_cases_in_denominator":True}
        save(folder/"summary.json",result);return result
    finally:generator.close();judge_client.close()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--day6",required=True,type=Path)
    p.add_argument("--phase",required=True,choices=("dev","test"));args=p.parse_args()
    plan=read(ROOT/"config/advanced.json")
    if args.phase=="test":
        selection=read(OUT/"selection.json");assert selection["sha256"]==hashes(),"Phiên bản khác lúc chốt."
        names=list(dict.fromkeys(["baseline",selection["selected_configuration"]]))
    else:
        assert not (OUT/"test").exists(),"Đã có test, không chọn lại."
        names=list(plan["configurations"])
    queries=read(BENCH/f"{args.phase}_queries.json")
    store=DocumentStore(ROOT/"starter/data/advanced",args.day6.resolve())
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures=[pool.submit(execute,name,plan["configurations"][name],args.phase,queries,store) for name in names]
        summaries=[f.result() for f in futures]
    save(OUT/f"{args.phase}_comparison.json",summaries)
    save(OUT/"data_provenance.json",{"document":read(ROOT/"starter/data/advanced/manifest.json"),"vector_store":store.vector_info})
    if args.phase=="dev":
        best=min(summaries,key=lambda s:(s["errors"],-s["passed"],s["total_cost_upper_usd"]))
        save(OUT/"selection.json",{"selected_configuration":best["configuration"],"sha256":hashes(),
             "fixed_at_utc":datetime.now(timezone.utc).isoformat(),"test_used_for_selection":False})


if __name__=="__main__":main()
