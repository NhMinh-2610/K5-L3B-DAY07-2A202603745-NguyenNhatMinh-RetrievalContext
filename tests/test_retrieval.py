"""Kiểm tra filter, fusion, ngăn gold và mẫu số; không thay benchmark thật."""
import unittest

from src.retrieval import LexicalRetriever, pack_context, reciprocal_rank_fusion, validate_query
from src.retrieval_metrics import evaluate_trace, evidence_hit, summarize


def chunk(identifier, text, section="1.1", page=1, score=1.0):
    return {"id": identifier, "text": text, "source_id": "doc", "source": "https://example.org/doc",
            "page": page, "metadata": {"section": section}, "score": score}


class RetrievalTests(unittest.TestCase):
    def test_filter_applies_before_top_k(self):
        index = LexicalRetriever([chunk("wrong", "alpha", "1.2"), chunk("right", "alpha beta")])
        results = index.search("alpha", filters={"section": "1.1"}, top_k=1)
        self.assertEqual([row["id"] for row in results], ["right"])

    def test_rrf_uses_ranks_and_records_both_sources(self):
        result = reciprocal_rank_fusion({
            "dense": [chunk("a", "A", score=1000000), chunk("b", "B", score=0.1)],
            "tfidf": [chunk("b", "B", score=0.001), chunk("c", "C", score=0.0005)],
        }, constant=60, top_k=3)
        self.assertEqual(result[0]["id"], "b")
        self.assertEqual(len(result[0]["components"]), 2)
        self.assertAlmostEqual(result[0]["score"], 1 / 61 + 1 / 62)

    def test_rrf_rejects_duplicate_or_conflicting_chunks(self):
        with self.assertRaises(ValueError):
            reciprocal_rank_fusion({"dense": [chunk("a", "A"), chunk("a", "A")]}, constant=60, top_k=3)
        with self.assertRaises(ValueError):
            reciprocal_rank_fusion({"dense": [chunk("a", "A")], "tfidf": [chunk("a", "different")]},
                                   constant=60, top_k=3)

    def test_query_rejects_gold_and_label(self):
        query = {"id": "q", "split": "dev", "question": "alpha?", "filter": {}}
        validate_query(query)
        for field, value in (("gold", []), ("expected_answer", "alpha"), ("answerable", True)):
            with self.assertRaises(ValueError):
                validate_query({**query, field: value})

    def test_context_keeps_whole_chunks_and_counts_headers(self):
        first, second = chunk("a", "alpha"), chunk("b", "beta")
        full, ids = pack_context([first, first, second], budget_chars=1000)
        self.assertEqual(ids, ["a", "b"])
        small, ids = pack_context([first, second], budget_chars=len(full) - 1)
        self.assertEqual(ids, ["a"])
        self.assertIn(first["text"], small)
        self.assertNotIn(second["text"], small)

    def test_hit_requires_correct_source_and_page(self):
        gold = [{"source_id": "doc", "page": 1, "evidence": "alpha beta"}]
        self.assertTrue(evidence_hit(chunk("a", "alpha\n beta"), gold))
        self.assertFalse(evidence_hit(chunk("a", "alpha beta", page=2), gold))

    def test_multi_chunk_context_does_not_inflate_ranking(self):
        trace = {"query_id": "q", "method": "dense", "results": [chunk("a", "alpha"), chunk("b", "beta")],
                 "context_ids": ["a", "b"], "context": "alpha beta", "retrieval_ms": 1,
                 "query_embedding_ms_shared": 2}
        case = {"id": "q", "answerable": True,
                "gold": [{"source_id": "doc", "page": 1, "evidence": "alpha beta"}]}
        check = {"query_id": "q", "evidence": [{"source_id": "doc", "page": 1,
                                                 "supporting_chunk_ids": ["a", "b"]}]}
        result = evaluate_trace(trace, case, check)
        self.assertFalse(result["hit1"])
        self.assertFalse(result["hit3"])
        self.assertTrue(result["prepared_context_has_evidence"])

    def test_unanswerable_is_excluded_from_retrieval_denominator(self):
        answerable = {"method": "dense", "answerable": True, "hit1": True, "hit3": True,
                      "prepared_context_has_evidence": True, "retrieval_ms": 1,
                      "query_embedding_ms_shared": 2, "context": "alpha"}
        trace = {"query_id": "u", "method": "dense", "results": [], "context_ids": [], "context": "",
                 "retrieval_ms": 1, "query_embedding_ms_shared": 2}
        unanswerable = evaluate_trace(trace, {"id": "u", "answerable": False}, {"query_id": "u"})
        result = summarize([answerable, unanswerable], ["dense"])[0]
        self.assertEqual(result["answerable_n"], 1)
        self.assertEqual(result["unanswerable_n"], 1)
        self.assertEqual(result["hit1_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
