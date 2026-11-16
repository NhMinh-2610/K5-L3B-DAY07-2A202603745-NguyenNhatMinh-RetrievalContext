"""Tạo và kiểm tra benchmark Day 7; không chạy retrieval hoặc gọi model."""
import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from prepare_day6 import ROOT, normalize, read_json, read_jsonl, require, sha256


BENCHMARK = ROOT / "benchmark"
IMPORTED = ROOT / "starter/data/day6"
QUERY_FIELDS = ("id", "split", "question", "filter")


def case_hash(case):
    data = json.dumps(case, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def query_input(case):
    return {field: case[field] for field in QUERY_FIELDS}


def trace_evidence(gold, units, chunks):
    quote = gold["evidence"]
    for unit in units:
        if (unit["document_id"], unit["page"]) != (gold["source_id"], gold["page"]):
            continue
        offset = unit["text"].find(quote)
        if offset < 0:
            continue
        start = unit["page_char_start"] + offset
        end = start + len(quote)
        covered, supporting = bytearray(len(quote)), []
        ordered = sorted((c for c in chunks if c["source_id"] == gold["source_id"]
                          and c["page"] == gold["page"]
                          and c["metadata"].get("unit_id") == unit["unit_id"]),
                         key=lambda c: c["metadata"]["page_char_start"])
        for chunk in ordered:
            meta = chunk["metadata"]
            left, right = max(start, meta["page_char_start"]), min(end, meta["page_char_end"])
            if left >= right:
                continue
            require(chunk["text"] == unit["text"][meta["unit_char_start"]:meta["unit_char_end"]],
                    "Nội dung chunk không khớp vị trí trong nguồn.")
            covered[left - start:right - start] = b"\x01" * (right - left)
            supporting.append(chunk["id"])
        require(all(mark or char.isspace() for mark, char in zip(covered, quote)),
                "Các chunk chưa phủ đủ bằng chứng trong nguồn.")
        return {"page_char_start": start, "page_char_end": end,
                "supporting_chunk_ids": supporting}
    raise ValueError("Cần giữ nguyên trích dẫn nguồn để xác định vị trí evidence và các chunk.")


def validate_cases(cases):
    ids, questions = set(), set()
    counts = Counter()
    for case in cases:
        require(isinstance(case.get("id"), str) and case["id"].strip()
                and case["id"] not in ids, "ID câu hỏi trống hoặc bị trùng.")
        require(case.get("split") in ("dev", "test"), "Split phải là dev hoặc test.")
        require(isinstance(case.get("question"), str) and case["question"].strip(),
                f"Thiếu câu hỏi ở {case['id']}.")
        text = normalize(case["question"]).casefold()
        require(text not in questions, "Câu hỏi bị trùng giữa các trường hợp.")
        require(isinstance(case.get("filter"), dict), f"Filter không hợp lệ ở {case['id']}.")
        require(type(case.get("answerable")) is bool, f"Thiếu nhãn answerable ở {case['id']}.")
        if case["answerable"]:
            require(isinstance(case.get("expected_answer"), str) and case["expected_answer"].strip()
                    and isinstance(case.get("gold"), list) and case["gold"],
                    f"Thiếu đáp án hoặc bằng chứng ở {case['id']}.")
            for gold in case["gold"]:
                require(isinstance(gold.get("source_id"), str) and gold["source_id"].strip()
                        and type(gold.get("page")) is int and gold["page"] > 0
                        and isinstance(gold.get("evidence"), str) and gold["evidence"].strip(),
                        f"Nguồn, trang hoặc bằng chứng không hợp lệ ở {case['id']}.")
        else:
            require("gold" not in case and "expected_answer" not in case,
                    f"Câu thiếu bằng chứng không được có gold hoặc đáp án: {case['id']}.")
            check = case.get("absence_check", {})
            require(case.get("expected_behavior") == "search_and_abstain"
                    and isinstance(case.get("absence_reason"), str) and case["absence_reason"].strip()
                    and isinstance(check.get("search_patterns"), list) and check["search_patterns"]
                    and isinstance(check.get("related_pages"), list) and check["related_pages"],
                    f"Thiếu cách kiểm tra thông tin vắng mặt ở {case['id']}.")
        ids.add(case["id"])
        questions.add(text)
        counts[(case["split"], case["answerable"])] += 1
    for split, answerable, minimum in (("dev", True, 15), ("dev", False, 2),
                                       ("test", True, 5), ("test", False, 2)):
        require(counts[(split, answerable)] >= minimum,
                f"Chưa đủ câu {split}, answerable={answerable}: cần ít nhất {minimum}.")
    return {split: {"answerable": counts[(split, True)], "unanswerable": counts[(split, False)]}
            for split in ("dev", "test")}


def prepare(source):
    imported_manifest = read_json(IMPORTED / "manifest.json")
    source_config = read_json(source / "starter/strategies.json")
    corpus_path = source / source_config["corpus_path"]
    corpus_hash = sha256(corpus_path)
    require(corpus_hash == imported_manifest["source_files_sha256"][source_config["corpus_path"]],
            "Corpus Day 6 đã thay đổi; cần chuyển lại dữ liệu trước khi chuẩn bị benchmark.")
    chunks = read_json(IMPORTED / "chunks.json")
    cases = read_json(IMPORTED / "questions_dev.json") + read_json(BENCHMARK / "new_cases.json")
    counts = validate_cases(cases)
    old_test = [q for q in read_jsonl(source / "benchmark/questions.jsonl") if q["split"] == "test"]
    old_ids = {q["id"] for q in old_test}
    old_text = {normalize(q["question"]).casefold() for q in old_test}
    require(all(q["id"] not in old_ids and normalize(q["question"]).casefold() not in old_text
                for q in cases if q["split"] == "test"), "Không dùng lại câu test Day 6.")

    units = read_jsonl(corpus_path)
    pages = defaultdict(list)
    for unit in units:
        pages[(unit["document_id"], unit["page"])].append(unit["text"])
    pages = {key: normalize("\n".join(parts)) for key, parts in pages.items()}
    documents = {doc["source_id"]: doc for doc in imported_manifest["source_documents"]}
    source_checks = []
    for case in cases:
        result = {"query_id": case["id"], "split": case["split"], "answerable": case["answerable"]}
        if case["answerable"]:
            evidence = []
            for gold in case["gold"]:
                key = (gold["source_id"], gold["page"])
                require(gold["source_id"] in documents
                        and normalize(gold["evidence"]) in pages.get(key, ""),
                        f"Bằng chứng không khớp corpus ở {case['id']}, trang {gold['page']}.")
                evidence.append({"source_id": gold["source_id"], "page": gold["page"],
                                 "source": documents[gold["source_id"]]["source_path_or_url"],
                                 "found_in_source_text": True,
                                 **trace_evidence(gold, units, chunks),
                                 "single_chunk_ids": [c["id"] for c in chunks
                                                      if (c["source_id"], c["page"]) == key
                                                      and normalize(gold["evidence"]) in normalize(c["text"])]})
            result["evidence"] = evidence
            result["has_single_chunk_evidence"] = any(e["single_chunk_ids"] for e in evidence)
        else:
            check = case["absence_check"]
            included_pages = {page for _, page in pages}
            require(set(check["related_pages"]) <= included_pages,
                    f"Trang kiểm tra nằm ngoài corpus ở {case['id']}.")
            matches = []
            for pattern in check["search_patterns"]:
                require(isinstance(pattern, str) and pattern.strip(), "Mẫu tìm kiếm không hợp lệ.")
                regex = re.compile(pattern, re.IGNORECASE)
                matches.append({"pattern": pattern,
                                "pages": sorted({u["page"] for u in units if regex.search(u["text"])})})
            require(any(row["pages"] for row in matches),
                    f"Không tìm thấy chủ đề liên quan trong corpus cho {case['id']}.")
            result.update(scope="indexed_corpus", pages_scanned=len(pages),
                          search_results=matches, related_pages=check["related_pages"],
                          absence_reason=case["absence_reason"],
                          limitation="Tìm từ khóa không tự chứng minh thiếu bằng chứng; cần đọc nguồn liên quan.")
        source_checks.append(result)

    outputs = {}
    for split in ("dev", "test"):
        selected = [q for q in cases if q["split"] == split]
        outputs[f"{split}.json"] = selected
        outputs[f"{split}_queries.json"] = [query_input(q) for q in selected]
    outputs["cases.json"] = [{key: q[key] for key in ("id", "split", "answerable")} for q in cases]
    outputs["source_checks.json"] = source_checks
    for split in ("dev", "test"):
        outputs[f"{split}_source_checks.json"] = [row for row in source_checks if row["split"] == split]
    BENCHMARK.mkdir(parents=True, exist_ok=True)
    for name, data in outputs.items():
        (BENCHMARK / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    review_path = BENCHMARK / "review.csv"
    previous = {}
    if review_path.exists():
        with review_path.open(encoding="utf-8-sig", newline="") as stream:
            previous = {row["id"]: row for row in csv.DictReader(stream)}
    reviews = []
    for case in cases:
        digest = case_hash(case)
        old = previous.get(case["id"], {})
        unchanged = old.get("case_sha256") == digest
        page_numbers = sorted({g["page"] for g in case.get("gold", [])}
                              or set(case["absence_check"]["related_pages"]))
        reviews.append({"id": case["id"], "split": case["split"], "question": case["question"],
                        "pages": ";".join(map(str, page_numbers)), "case_sha256": digest,
                        "status": old.get("status", "pending") if unchanged else "pending",
                        "note": old.get("note", "") if unchanged else ""})
    require(all(row["status"] in ("pending", "confirmed", "needs_changes") for row in reviews),
            "Trạng thái rà nguồn chỉ nhận pending, confirmed hoặc needs_changes.")
    with review_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(reviews[0]))
        writer.writeheader()
        writer.writerows(reviews)

    validation = {
        "format_and_source_text_check": "passed", "total_questions": len(cases), "counts": counts,
        "corpus_sha256": corpus_hash, "included_content_pages": len(pages),
        "all_gold_found_in_source_text": True, "all_gold_traceable_to_chunks": True,
        "old_test_questions_reused": False,
        "queries_contain_only": list(QUERY_FIELDS),
        "questions_without_single_chunk_evidence": [q["query_id"] for q in source_checks
                                                    if q["answerable"] and not q["has_single_chunk_evidence"]],
        "source_review": dict(Counter(row["status"] for row in reviews)),
        "scope": "Kiểm tra dữ liệu; chưa phải kết quả retrieval, agent hay chấm câu trả lời.",
    }
    split_definition = {
        "benchmark_version": "day7-v1", "counts": counts,
        "dev_ids": [q["id"] for q in cases if q["split"] == "dev"],
        "test_ids": [q["id"] for q in cases if q["split"] == "test"],
        "corpus_sha256": corpus_hash, "chunks_sha256": sha256(IMPORTED / "chunks.json"),
        "files_sha256": {name: sha256(BENCHMARK / name) for name in
                         ("new_cases.json", "dev.json", "test.json", "dev_queries.json", "test_queries.json",
                          "dev_source_checks.json", "test_source_checks.json", "cases.json")},
        "retrieval_cutoffs": [1, 3], "retrieval_denominator": "answerable_questions_only",
        "ranking_evidence_rule": "Một chunk đúng nguồn/trang chứa đủ một evidence thay thế, sau NFKC và gộp khoảng trắng.",
        "context_evidence_rule": "Đủ một evidence thay thế trong context thực gửi model; có thể cần nhiều chunk đúng nguồn/trang.",
        "test_policy": "Chọn và chỉnh trên dev; chốt cấu hình trước khi chạy baseline và cấu hình chọn trên cùng test.",
    }
    for name, data in (("validation.json", validation), ("split.json", split_definition)):
        (BENCHMARK / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return validation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--day6", required=True, help="Thư mục gốc repo Day 6")
    args = parser.parse_args()
    result = prepare(Path(args.day6).resolve())
    counts = result["counts"]
    print(f"Đã chuẩn bị {result['total_questions']} câu: "
          f"dev {counts['dev']['answerable']} + {counts['dev']['unanswerable']}, "
          f"test {counts['test']['answerable']} + {counts['test']['unanswerable']}.")
    print("Định dạng và bằng chứng trong text nguồn: đạt.")
    print(f"Trạng thái rà nguồn: {result['source_review']}")
    print("Chưa chạy benchmark hoặc gọi model.")


if __name__ == "__main__":
    main()
