"""Kiểm tra nhãn, mẫu số và tiêu chí chọn trước khi chấm API thật."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from complete_lab import selection_key
from src.evaluation import aggregate, validate_review


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.case = {"id": "q", "answerable": True,
                     "gold": [{"source_id": "doc", "page": 1, "evidence": "alpha beta"}]}
        chunk = {"id": "a", "source_id": "doc", "page": 1, "text": "alpha beta"}
        self.trace = {"query_id": "q", "status": "answered", "citations": ["a"], "context_ids": ["a"],
                      "search_count": 1, "elapsed_seconds": 1,
                      "events": [{"event": "search", "status": "complete", "results": [chunk]}]}
        self.review = {"query_id": "q", "answer_grade": 2, "context_grade": 2,
                       "citation_support": [True], "citation_reasons": ["Nguồn đủ ý."],
                       "abstention_correct": False, "answer_reason": "Đủ ý.",
                       "context_reason": "Có evidence.", "abstention_reason": ""}

    def test_citation_labels_must_match_actual_citations(self):
        with self.assertRaises(ValueError):
            validate_review({**self.review, "citation_support": []}, self.case, self.trace)

    def test_answerable_abstention_cannot_receive_positive_score(self):
        trace = {**self.trace, "status": "abstain", "citations": []}
        review = {**self.review, "citation_support": [], "citation_reasons": []}
        with self.assertRaises(ValueError):
            validate_review(review, self.case, trace)

    def test_correct_abstention_requires_actual_abstain_status(self):
        with self.assertRaises(ValueError):
            validate_review({**self.review, "abstention_correct": True}, {"answerable": False}, self.trace)

    def test_errors_do_not_inflate_selection_score(self):
        error_case = {**copy.deepcopy(self.case), "id": "error"}
        checks = [{"query_id": "q", "evidence": [{"supporting_chunk_ids": ["a"]}]}]
        result = aggregate([self.case, error_case],
                           [self.trace, {"query_id": "error", "status": "error", "elapsed_seconds": 2}],
                           [self.review], checks)
        self.assertEqual(result["answer_mean"], 2)
        self.assertEqual(result["answer_score_over_expected"], 0.5)
        self.assertEqual(result["errors"], 1)

    def test_selection_prefers_complete_runs_before_partial_scores(self):
        metrics = {"errors": 0, "answer_score_over_expected": 0.8,
                   "abstention": {"rate": 1}, "false_abstention": {"rate": 0},
                   "citation_validity": {"rate": 1}, "context_semantic": {"rate": 0.8}, "median_seconds": 1}
        complete = {"metrics": metrics, "total_cost_upper_usd": 0.1}
        failed = {"metrics": {**metrics, "errors": 1, "answer_score_over_expected": 0.9}, "total_cost_upper_usd": 0.01}
        self.assertLess(selection_key(complete), selection_key(failed))


if __name__ == "__main__":
    unittest.main()
