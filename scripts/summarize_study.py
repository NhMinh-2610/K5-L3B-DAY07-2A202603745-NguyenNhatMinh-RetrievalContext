"""Tổng hợp kết quả đã lưu và bản rà nguồn, không gọi model hay chạy lại test."""
import copy
import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.evaluation import aggregate
from export_results import public_review

STUDY = ROOT / "results/study"


def read(path):
    if not path.exists():
        entry = public_entry(path)
        if entry:
            return json.loads((ROOT / entry["public_path"]).read_text(encoding="utf-8-sig"))
    return json.loads(path.read_text(encoding="utf-8-sig"))


def public_entry(path):
    manifest_path = ROOT / "results/exports.json"
    if not manifest_path.exists():
        return None
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    entry = manifest["files"].get(path.relative_to(ROOT).as_posix())
    if entry:
        actual = hashlib.sha256((ROOT / entry["public_path"]).read_bytes()).hexdigest()
        assert actual == entry["public_sha256"], "Bản xuất công khai đã thay đổi."
    return entry


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def digest(path):
    if not path.exists():
        entry = public_entry(path)
        if entry:
            return entry["raw_sha256"]
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    selection = read(STUDY / "selection.json")
    locked = {**selection["core_sha256"], **selection["config_sha256"],
              **selection["dev_summaries_sha256"],
              "config/experiment_plan.json": selection["plan_sha256"],
              "benchmark/split.json": selection["benchmark_sha256"]}
    assert all(digest(ROOT / name) == value for name, value in locked.items()), "Phiên bản đã chốt thay đổi."
    audit = read(STUDY / "test/source_audit.json")
    cases = read(ROOT / "benchmark/test.json")
    checks = read(ROOT / "benchmark/test_source_checks.json")
    reviewed = []
    for summary in read(STUDY / "test_comparison.json"):
        identifier = summary["configuration"]
        folder = STUDY / "test" / identifier
        assert digest(folder / "traces.json") == audit["traces_sha256"][identifier], "Trace đã thay đổi sau rà."
        traces = read(folder / "traces.json")
        reviews = copy.deepcopy(read(folder / "reviews.json"))
        notes = {row["query_id"]: row for row in audit["cases"] if row["configuration"] == identifier}
        assert set(notes) == {row["id"] for row in cases}, "Chưa rà đủ câu."
        for review in reviews:
            note = notes[review["query_id"]]
            for field, value in note["overrides"].items():
                assert field in {"answer_grade", "context_grade", "citation_support", "citation_reasons",
                                 "answer_reason", "context_reason"}
                review[field] = value
            review["review_status"] = "source_check_proposed"
            review["source_audit_note"] = note["note"]
        if (folder / "traces.json").exists():
            save(folder / "reviews_source_checked.json", reviews)
        else:
            assert read(folder / "reviews_source_checked.public.json") == [public_review(row) for row in reviews], "Bản rà đã đổi; cần xuất lại kết quả có nguồn gốc tương ứng."
        result = copy.deepcopy(summary)
        result["metrics"] = aggregate(cases, traces, reviews, checks)
        result["metrics"]["label_origin"] = audit["label_origin"]
        result["semantic_labels"] = "source_check_proposed"
        result["raw_api_metrics"] = summary["metrics"]
        reviewed.append(result)
    save(STUDY / "test_reviewed_comparison.json", reviewed)

    summaries = read(STUDY / "dev_comparison.json") + reviewed
    columns = ["split", "configuration", "answer_mean", "answer_0", "answer_1", "answer_2",
               "hit1", "hit3", "context_exact", "context_semantic", "citation_validity",
               "abstention", "false_abstention", "tool_use", "errors", "median_seconds",
               "generation_cost_upper_usd", "judge_cost_upper_usd", "total_cost_upper_usd", "label_origin"]
    with (STUDY / "comparison.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for summary in summaries:
            metrics = summary["metrics"]
            row = {key: summary[key] for key in ("split", "configuration", "generation_cost_upper_usd",
                                                "judge_cost_upper_usd", "total_cost_upper_usd")}
            row.update({key: metrics[key] for key in ("answer_mean", "errors", "median_seconds", "label_origin")})
            row.update({f"answer_{i}": metrics["answer_grades"][str(i)] for i in (0, 1, 2)})
            for column, key in {"hit1": "first_search_hit1", "hit3": "first_search_evidence_hit3",
                                "context_exact": "context_exact", "context_semantic": "context_semantic",
                                "citation_validity": "citation_validity", "abstention": "abstention",
                                "false_abstention": "false_abstention", "tool_use": "tool_use"}.items():
                value = metrics[key]
                row[column] = f"{value['n']}/{value['N']}"
            writer.writerow(row)
    raw = read(STUDY / "dev_comparison.json") + read(STUDY / "test_comparison.json")
    web = [read(path) for path in (ROOT / "results/web").glob("web_*.json")]
    previous_costs = read(STUDY / "costs.json") if (STUDY / "costs.json").exists() else {}
    save(STUDY / "costs.json", {
        "scope": "Các lần chạy nghiên cứu và web có trace lưu trong repo; không phải toàn bộ lịch sử tài khoản.",
        "cost_is_invoice": False,
        "pricing": raw[0]["config"]["pricing"],
        "study_generation_upper_usd": sum(row["generation_cost_upper_usd"] for row in raw),
        "study_judge_upper_usd": sum(row["judge_cost_upper_usd"] for row in raw),
        "study_total_upper_usd": sum(row["total_cost_upper_usd"] for row in raw),
        "study_api_requests": sum(row["api_requests"] for row in raw),
        "web_runs": len(web) if web else previous_costs.get("web_runs", 0),
        "web_total_upper_usd": sum(row["estimated_cost_upper_usd"] for row in web) if web else previous_costs.get("web_total_upper_usd", 0),
        "web_api_requests": sum(row["api_requests"] for row in web) if web else previous_costs.get("web_api_requests", 0),
        "historical_smoke_runs": "results/agent/: nằm ngoài tổng study/web ở trên; xem từng summary.json.",
    })
    print("Đã tổng hợp 5 cấu hình/split và 14 bản rà test; giữ nguyên kết quả API và phiên bản đã chốt.")


if __name__ == "__main__":
    main()
