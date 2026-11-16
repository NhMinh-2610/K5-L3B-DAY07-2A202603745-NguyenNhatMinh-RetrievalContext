"""Xuất kết quả lab có cấu trúc; không đưa hội thoại/request/response thô lên Git."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TRACE_FIELDS = ("query_id", "split", "question", "filter", "status", "answer", "citations",
                "citation_sources", "context", "context_ids", "search_count", "model_call_count",
                "elapsed_seconds", "citation_id_check", "semantic_review_status", "api_requests",
                "error", "error_type", "abstention_reason")
REVIEW_FIELDS = ("query_id", "review_status", "grader", "answer_grade", "context_grade",
                 "citation_support", "abstention_correct", "answer_reason", "context_reason",
                 "citation_reasons", "abstention_reason", "source_audit_note")
MODEL_FIELDS = ("model", "system_fingerprint", "usage", "finish_reason",
                "estimated_cost_upper_usd", "elapsed_ms", "image_inputs")


def pick(value, fields):
    return {key: value[key] for key in fields if key in value}


def public_trace(trace):
    result = pick(trace, TRACE_FIELDS)
    result["events"] = []
    for event in trace["events"]:
        kind = event["event"]
        if kind == "model_call":
            response = event.get("response", {})
            entry = {"event": kind, **pick(event, ("phase",)), **pick(response, MODEL_FIELDS)}
            entry["tool_calls"] = []
            for call in response.get("message", {}).get("tool_calls", []):
                function = call["function"]
                try:
                    arguments = json.loads(function["arguments"])
                except (ValueError, TypeError):
                    arguments = {"parse_error": True}
                entry["tool_calls"].append({"name": function["name"], "arguments": arguments})
        elif kind == "search":
            entry = pick(event, ("event", "tool", "arguments", "query", "filter", "status",
                                 "retrieval", "results", "context", "context_ids", "error", "error_type"))
        else:
            entry = pick(event, ("event", "tool", "arguments", "reason", "error", "error_type"))
        result["events"].append(entry)
    return result


def public_review(review):
    result = pick(review, REVIEW_FIELDS)
    if "judge_response" in review:
        result["grading_metadata"] = pick(review["judge_response"], MODEL_FIELDS)
    elif "grading_metadata" in review:
        result["grading_metadata"] = pick(review["grading_metadata"], MODEL_FIELDS)
    return result


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = {"policy": "Chỉ kết quả và trace tool của lab; bỏ request/messages, phản hồi model thô và hội thoại trợ lý.",
                "raw_files_committed": False, "files": {}}
    manifest_path = ROOT / "results/exports.json"
    if manifest_path.exists():
        previous = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        for name, entry in previous["files"].items():
            if not (ROOT / name).exists():
                assert digest(ROOT / entry["public_path"]) == entry["public_sha256"], "Bản xuất đã thay đổi."
                manifest["files"][name] = entry
    paths = sorted((ROOT / "results/agent").glob("*/traces.json"))
    for pattern in ("*/*/traces.json", "*/*/reviews.json", "*/*/reviews_source_checked.json"):
        paths.extend(sorted((ROOT / "results/study").glob(pattern)))
    for pattern in ("*/*/*/traces.json", "*/*/*/reviews.json"):
        paths.extend(sorted((ROOT / "results/extension").glob(pattern)))
    for path in paths:
        rows = json.loads(path.read_text(encoding="utf-8-sig"))
        transform = public_trace if path.name == "traces.json" else public_review
        target = path.with_name(path.stem + ".public.json")
        target.write_text(json.dumps([transform(row) for row in rows], ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8")
        manifest["files"][path.relative_to(ROOT).as_posix()] = {
            "raw_sha256": digest(path), "public_path": target.relative_to(ROOT).as_posix(),
            "public_sha256": digest(target), "rows": len(rows)}
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Đã xuất {len(paths)} file kết quả, không kèm hội thoại AI thô.")


if __name__ == "__main__":
    main()
