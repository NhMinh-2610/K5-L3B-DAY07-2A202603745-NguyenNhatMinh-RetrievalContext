"""Mở rộng chunk bằng hàng xóm cùng trang/mục, không dùng nhãn benchmark."""
import hashlib
from collections import defaultdict


def make_groups(chunks, radius=1):
    if type(radius) is not int or not 0 <= radius <= 3:
        raise ValueError("Bán kính lân cận phải từ 0 đến 3.")
    pages = defaultdict(list)
    for chunk in chunks:
        pages[(chunk["source_id"], chunk["page"], chunk["metadata"].get("section"))].append(chunk)
    groups = {}
    for rows in pages.values():
        rows.sort(key=lambda row: (row["metadata"].get("page_char_start", 0), row["id"]))
        for position, seed in enumerate(rows):
            members = rows[max(0, position-radius):position+radius+1]
            ids = [row["id"] for row in members]
            identifier = "group_" + hashlib.sha256("|".join(ids).encode()).hexdigest()[:24]
            groups[seed["id"]] = {**seed, "id": identifier,
                                   "text": "\n".join(row["text"] for row in members),
                                   "metadata": {**seed["metadata"], "source_chunk_ids": ids,
                                                "context_expansion": "same_page_same_section",
                                                "neighbor_radius": radius}}
    return groups


class NeighborRetriever:
    def __init__(self, base, chunks, radius=1):
        self.base = base
        self.groups = make_groups(chunks, radius)
        self.chunks = list({row["id"]: row for row in self.groups.values()}.values())

    def search(self, query, **kwargs):
        result = self.base.search(query, **kwargs)
        seeds = result["results"]
        expanded, seen = [], set()
        for seed in seeds:
            group = self.groups[seed["id"]]
            if group["id"] in seen:
                continue
            seen.add(group["id"])
            expanded.append({**group, "score": seed["score"], "rank": len(expanded)+1,
                             "strategy": seed["strategy"], "seed_chunk_id": seed["id"]})
        return {**result, "results": expanded, "seed_results": seeds,
                "context_expansion": "same_page_same_section"}
