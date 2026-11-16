"""TF-IDF, hợp nhất RRF và chọn context; không dùng đáp án benchmark."""
import math

from starter.baseline import TfidfIndex


FILTER_FIELDS = {"section", "language", "year", "document_type"}
QUERY_FIELDS = {"id", "split", "question", "filter"}


def validate_filters(filters):
    if not isinstance(filters, dict) or set(filters) - FILTER_FIELDS:
        raise ValueError("Trường lọc metadata không hợp lệ.")
    for value in filters.values():
        if not isinstance(value, (str, int, float, bool)) or value == "":
            raise ValueError("Giá trị filter phải là giá trị đơn, không rỗng.")
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("Filter không nhận số vô hạn hoặc NaN.")


def validate_query(query):
    if set(query) != QUERY_FIELDS:
        raise ValueError("Đầu vào chỉ nhận ID, split, câu hỏi và filter; không nhận gold hoặc nhãn.")
    if not isinstance(query["id"], str) or not query["id"].strip():
        raise ValueError("ID câu hỏi không được rỗng.")
    if query["split"] not in ("dev", "test"):
        raise ValueError("Split không hợp lệ.")
    if not isinstance(query["question"], str) or not query["question"].strip():
        raise ValueError("Câu hỏi không được rỗng.")
    validate_filters(query["filter"])


class LexicalRetriever:
    def __init__(self, chunks):
        self.index = TfidfIndex(chunks)
        self.chunk_count = len(chunks)

    def search(self, question, *, filters, top_k):
        validate_filters(filters)
        if type(top_k) is not int or top_k < 1:
            raise ValueError("top_k phải là số nguyên dương.")
        # Tính IDF trên cùng corpus; lọc trước khi cắt top-k.
        ranked = self.index.search(question, top_k=self.chunk_count)
        return [chunk for chunk in ranked
                if all(chunk["metadata"].get(key) == value for key, value in filters.items())][:top_k]


def reciprocal_rank_fusion(rankings, *, constant, top_k):
    if type(constant) is not int or constant < 1 or type(top_k) is not int or top_k < 1:
        raise ValueError("Hằng số RRF và top_k phải là số nguyên dương.")
    merged = {}
    for method, results in rankings.items():
        seen = set()
        for rank, chunk in enumerate(results, 1):
            if chunk["id"] in seen:
                raise ValueError("Một danh sách xếp hạng không được trùng ID.")
            seen.add(chunk["id"])
            if chunk["id"] not in merged:
                merged[chunk["id"]] = {**chunk, "score": 0.0, "strategy": "hybrid", "components": []}
            target = merged[chunk["id"]]
            if any(target[key] != chunk[key] for key in ("text", "source_id", "source", "page", "metadata")):
                raise ValueError("Cùng ID nhưng nội dung giữa các retriever không khớp.")
            contribution = 1 / (constant + rank)
            target["score"] += contribution
            target["components"].append({"method": method, "rank": rank,
                                         "original_score": chunk["score"], "rrf_contribution": contribution})
    return sorted(merged.values(), key=lambda row: (-row["score"], row["id"]))[:top_k]


def pack_context(results, *, budget_chars):
    if type(budget_chars) is not int or budget_chars < 1:
        raise ValueError("Context budget phải là số nguyên dương.")
    blocks, ids = [], []
    for chunk in results:
        if chunk["id"] in ids:
            continue
        block = f"[{chunk['id']} | {chunk['source']} | page {chunk['page']}]\n{chunk['text']}"
        if len("\n\n".join(blocks + [block])) <= budget_chars:
            blocks.append(block)
            ids.append(chunk["id"])
    return "\n\n".join(blocks), ids
