"""Chấm retrieval sau truy xuất; tách câu thiếu bằng chứng khỏi mẫu số."""
import statistics
import unicodedata


def normalize(text):
    return " ".join(unicodedata.normalize("NFKC", text).split())


def evidence_hit(chunk, gold):
    return any(chunk["source_id"] == item["source_id"] and chunk["page"] == item["page"]
               and normalize(item["evidence"]) in normalize(chunk["text"]) for item in gold)


def evaluate_trace(trace, case, source_check):
    if trace["query_id"] != case["id"] or trace["query_id"] != source_check["query_id"]:
        raise ValueError("Trace và nhãn không cùng câu hỏi.")
    if not case["answerable"]:
        return {**trace, "answerable": False, "hit1": None, "hit3": None,
                "prepared_context_has_evidence": None}
    context_ids = set(trace["context_ids"])
    supported = False
    for gold, check in zip(case["gold"], source_check["evidence"], strict=True):
        if (gold["source_id"], gold["page"]) != (check["source_id"], check["page"]):
            raise ValueError("Nhãn evidence và vị trí nguồn không khớp.")
        required_ids = set(check["supporting_chunk_ids"])
        supported |= bool(required_ids and required_ids <= context_ids)
    return {**trace, "answerable": True,
            "hit1": bool(trace["results"] and evidence_hit(trace["results"][0], case["gold"])),
            "hit3": any(evidence_hit(chunk, case["gold"]) for chunk in trace["results"][:3]),
            "prepared_context_has_evidence": supported}


def summarize(traces, methods):
    rows = []
    for method in methods:
        selected = [row for row in traces if row["method"] == method]
        answerable = [row for row in selected if row["answerable"]]
        n = len(answerable)
        if not n:
            raise ValueError("Không có câu có đáp án để tính retrieval metrics.")
        rows.append({"method": method, "split": "dev", "queries": len(selected),
                     "answerable_n": n, "unanswerable_n": len(selected) - n,
                     "hit1_n": sum(row["hit1"] for row in answerable),
                     "hit1_rate": sum(row["hit1"] for row in answerable) / n,
                     "evidence_hit3_n": sum(row["hit3"] for row in answerable),
                     "evidence_hit3_rate": sum(row["hit3"] for row in answerable) / n,
                     "prepared_context_evidence_n": sum(row["prepared_context_has_evidence"] for row in answerable),
                     "prepared_context_evidence_rate": sum(row["prepared_context_has_evidence"] for row in answerable) / n,
                     "median_retrieval_ms": statistics.median(row["retrieval_ms"] for row in selected),
                     "median_query_embedding_ms_shared": statistics.median(row["query_embedding_ms_shared"] for row in selected),
                     "median_context_chars": statistics.median(len(row["context"]) for row in selected),
                     "service_cost_usd": 0})
    return rows
