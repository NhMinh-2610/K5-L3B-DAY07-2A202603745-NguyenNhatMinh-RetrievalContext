"""Chuyển chunk và bộ dev Day 6 sang định dạng Day 7, không chạy retrieval."""
import argparse
import csv
import hashlib
import json
import unicodedata
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "starter/data/day6"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines()
            if line.strip()]


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize(text):
    return " ".join(unicodedata.normalize("NFKC", text).split())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def prepare(source):
    selection = read_json(source / "results/selection.json")
    strategies = read_json(source / "starter/strategies.json")
    embedding = read_json(source / "starter/embedding.json")
    ingestion = read_json(source / "results/ingestion.json")
    source_manifest = read_json(source / "data/manifest.json")
    strategy = selection.get("selected_strategy")
    require(selection.get("status") == "fixed" and strategy in strategies["strategies"],
            "Day 6 chưa có cấu hình được chốt hợp lệ.")

    fingerprint_paths = {
        "questions_sha256": "benchmark/questions.jsonl",
        "corpus_sha256": strategies["corpus_path"],
        "strategies_sha256": "starter/strategies.json",
        "embedding_sha256": "starter/embedding.json",
    }
    for key, relative_path in fingerprint_paths.items():
        require(sha256(source / relative_path) == selection["fingerprints"][key],
                f"File Day 6 đã thay đổi sau khi chốt: {relative_path}")
    require(selection["model_signature"] == ingestion["model_signature"],
            "Phiên bản embedding không khớp giữa cấu hình đã chọn và lần ingest.")

    settings = strategies["strategies"][strategy]
    chunk_strategy = settings.get("reuse_chunks_from", strategy)
    chunk_path = strategies["strategies"][chunk_strategy]["chunks_path"]
    raw_chunks = read_jsonl(source / chunk_path)
    chunks = [{"id": c["chunk_id"], "source_id": c["document_id"],
               "source": c["source"], "page": c["page"], "text": c["text"],
               "metadata": c["metadata"]} for c in raw_chunks]
    recorded_count = next(row["chunk_count"] for row in ingestion["strategies"]
                          if row["strategy"] == strategy)
    require(len(chunks) == recorded_count and len({c["id"] for c in chunks}) == len(chunks),
            "Số chunk hoặc ID không khớp kết quả ingest Day 6.")
    for chunk in chunks:
        require(all(isinstance(chunk[k], str) and chunk[k].strip()
                    for k in ("id", "source_id", "source", "text"))
                and type(chunk["page"]) is int and chunk["page"] > 0
                and isinstance(chunk["metadata"], dict), "Chunk thiếu nội dung hoặc nguồn.")

    queries = read_jsonl(source / "benchmark/dev_queries.jsonl")
    allowed_fields = {"id", "split", "question", "filter"}
    require(len(queries) >= 15 and len({q["id"] for q in queries}) == len(queries),
            "Bộ dev cần ít nhất 15 ID khác nhau.")
    for query in queries:
        require(set(query) == allowed_fields and query["split"] == "dev"
                and isinstance(query["id"], str) and query["id"].strip()
                and isinstance(query["question"], str) and query["question"].strip()
                and isinstance(query["filter"], dict),
                "Query dev chỉ được chứa ID, split, câu hỏi và filter; không chứa đáp án.")
    # Chỉ lấy gold của dev; không xuất câu hỏi hoặc nhãn test cũ.
    dev_gold = [q for q in read_jsonl(source / "benchmark/questions.jsonl")
                if q.get("split") == "dev"]
    require(len({q["id"] for q in dev_gold}) == len(dev_gold), "Gold dev bị trùng ID.")
    gold_by_id = {q["id"]: q for q in dev_gold}
    require(set(gold_by_id) == {q["id"] for q in queries},
            "Danh sách câu hỏi dev không khớp gold Day 6.")

    page_text = defaultdict(list)
    for unit in read_jsonl(source / strategies["corpus_path"]):
        page_text[(unit["document_id"], unit["page"])].append(unit["text"])
    page_text = {key: normalize("\n".join(parts)) for key, parts in page_text.items()}
    questions, evidence_audit = [], []
    for query in queries:
        original = gold_by_id[query["id"]]
        require(query["question"] == original["question"]
                and query["filter"] == original.get("filter", {}),
                f"Query và gold khác nhau ở {query['id']}.")
        require(isinstance(original.get("expected_answer"), str)
                and original["expected_answer"].strip(), f"Thiếu đáp án ở {query['id']}.")
        evidence = original.get("gold_evidence") or [{
            "source_id": original["gold_source_id"], "page": original["gold_page"],
            "quote": original["evidence_quote"],
        }]
        gold = [{"source_id": g["source_id"], "page": g["page"], "evidence": g["quote"]}
                for g in evidence]
        checks = []
        for item in gold:
            quote = item["evidence"]
            key = (item["source_id"], item["page"])
            require(isinstance(quote, str) and normalize(quote)
                    and normalize(quote) in page_text.get(key, ""),
                    f"Bằng chứng {query['id']} không khớp text nguồn/trang Day 6.")
            matching_ids = [c["id"] for c in chunks
                            if (c["source_id"], c["page"]) == key
                            and normalize(quote) in normalize(c["text"])]
            checks.append({"source_id": item["source_id"], "page": item["page"],
                           "found_in_source_text": True,
                           "single_chunk_ids": matching_ids})
        questions.append({**query, "answerable": True,
                          "expected_answer": original["expected_answer"], "gold": gold})
        evidence_audit.append({"query_id": query["id"], "evidence": checks,
                               "has_single_chunk_evidence": any(c["single_chunk_ids"] for c in checks)})

    with (source / "benchmark/review_checklist.csv").open(encoding="utf-8-sig", newline="") as stream:
        reviews = {row["id"]: row["student_status"] for row in csv.DictReader(stream)}
    pending_ids = [q["id"] for q in queries if reviews.get(q["id"]) != "dong_y"]
    source_files = set(fingerprint_paths.values()) | {
        chunk_path, "data/manifest.json", "results/selection.json", "results/ingestion.json",
        "benchmark/dev_queries.jsonl", "benchmark/review_checklist.csv",
    }
    document_fields = ("source_id", "title", "authors", "source_path_or_url", "doi",
                       "license_or_permission", "license_url", "attribution",
                       "file_sha256", "included_pages")
    manifest = {
        "source_repository": source.name,
        "source_strategy": strategy,
        "source_chunk_file": chunk_path,
        "source_files_sha256": {name: sha256(source / name) for name in sorted(source_files)},
        "source_documents": [{k: doc[k] for k in document_fields if k in doc}
                             for doc in source_manifest["documents"]],
        "included_content_pages": source_manifest["summary"]["included_content_pages"],
        "chunk_count": len(chunks),
        "dev_answerable_questions": len(questions),
        "dev_unanswerable_questions": 0,
        "test_questions": 0,
        "embedding": {**embedding, "model_signature": ingestion["model_signature"]},
        "questions_without_single_chunk_evidence": [row["query_id"] for row in evidence_audit
                                                     if not row["has_single_chunk_evidence"]],
        "questions_pending_pdf_review": pending_ids,
        "text_check": "NFKC và gộp khoảng trắng chỉ dùng để đối chiếu; nội dung xuất giữ nguyên.",
        "limitations": [
            "Chưa bổ sung câu thiếu bằng chứng và bộ test Day 7.",
            "Đối chiếu text bằng code không thay thế việc đọc PDF và chấm nội dung.",
            "Một số bằng chứng trải qua nhiều chunk; baseline mẫu chưa hỗ trợ trường hợp này.",
            "Chưa trích đầy đủ nội dung ảnh và quan hệ ô/cột của bảng trong PDF.",
        ],
    }
    outputs = {"chunks.json": chunks, "questions_dev.json": questions,
               "queries_dev.json": queries, "embedding.json": embedding,
               "evidence_audit.json": evidence_audit, "manifest.json": manifest}
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for name, data in outputs.items():
        (OUTPUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                                   encoding="utf-8")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--day6", required=True, type=Path, help="Thư mục gốc repo Day 6")
    args = parser.parse_args()
    manifest = prepare(args.day6.resolve())
    print(f"Đã xuất {manifest['chunk_count']} chunk và {manifest['dev_answerable_questions']} câu dev.")
    print(f"Thư mục: {OUTPUT.relative_to(ROOT)}")
    pending = ", ".join(manifest["questions_without_single_chunk_evidence"])
    print(f"Câu chưa có bằng chứng nằm trọn trong một chunk: {pending or 'không có'}.")
    print("Chưa chạy retrieval, benchmark hay gọi API.")


if __name__ == "__main__":
    main()
