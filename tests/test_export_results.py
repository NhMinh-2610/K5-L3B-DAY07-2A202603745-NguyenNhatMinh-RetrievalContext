"""Kiểm tra bản xuất Git không chứa hội thoại và vẫn giữ bằng chứng lab."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from export_results import public_review, public_trace


class ExportTests(unittest.TestCase):
    def test_raw_messages_and_unknown_top_level_fields_are_excluded(self):
        trace = {"query_id": "q", "answer": "Đáp án", "api_key": "PRIVATE_VALUE",
                 "events": [{"event": "model_call", "phase": "answer",
                             "request": {"messages": [{"content": "PRIVATE_VALUE"}]},
                             "response": {"model": "model", "usage": {"total_tokens": 5},
                                          "message": {"content": "PRIVATE_VALUE", "tool_calls": []}}}]}
        exported = public_trace(trace)
        self.assertNotIn("PRIVATE_VALUE", json.dumps(exported))
        self.assertEqual(exported["answer"], "Đáp án")
        self.assertEqual(exported["events"][0]["usage"]["total_tokens"], 5)

    def test_search_evidence_and_native_tool_arguments_remain_available(self):
        evidence = {"id": "c", "text": "Evidence", "page": 1}
        trace = {"query_id": "q", "context_ids": ["c"], "events": [
            {"event": "search", "query": "AI", "results": [evidence]},
            {"event": "model_call", "response": {"message": {"tool_calls": [
                {"function": {"name": "submit_answer", "arguments": '{"answer":"AI [c]"}'}}]}}}]}
        exported = public_trace(trace)
        self.assertEqual(exported["events"][0]["results"], [evidence])
        self.assertEqual(exported["events"][1]["tool_calls"][0]["arguments"], {"answer": "AI [c]"})

    def test_grading_dialogue_is_removed_without_changing_grade_or_origin(self):
        exported = public_review({"query_id": "q", "answer_grade": 1, "review_status": "model_proposed",
                                  "judge_request": [{"content": "PRIVATE_VALUE"}],
                                  "judge_response": {"model": "judge", "message": {"content": "PRIVATE_VALUE"}}})
        self.assertNotIn("PRIVATE_VALUE", json.dumps(exported))
        self.assertEqual(exported["answer_grade"], 1)
        self.assertEqual(exported["review_status"], "model_proposed")


if __name__ == "__main__":
    unittest.main()
