"""Kiểm tra vòng lặp tool, context, lỗi và chi phí; không gọi API thật."""
import copy
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from src.agent import run_agent
from src.deepseek_client import CostLimitError, DeepSeekClient, ProviderCallError, usage_cost_upper, validate_config


CONFIG = json.loads((Path(__file__).resolve().parents[1] / "config/agent.json").read_text(encoding="utf-8"))
QUERY = {"id": "q", "split": "dev", "question": "Alpha là gì?", "filter": {"section": "1.1"}}


def document(identifier="a", text="Alpha là một ví dụ."):
    return {"id": identifier, "text": text, "source_id": "doc", "source": "https://example.org/doc",
            "page": 1, "metadata": {"section": "1.1"}, "score": 0.9}


def completion(name, arguments):
    return {"message": {"role": "assistant", "content": None,
                        "tool_calls": [{"id": "call_1", "type": "function",
                                        "function": {"name": name, "arguments": json.dumps(arguments)}}]},
            "finish_reason": "tool_calls", "model": "unit-test-only", "usage": {}}


class Client:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.requests = []

    def complete(self, messages, tools, choice):
        self.requests.append(copy.deepcopy({"messages": messages, "tools": tools, "choice": choice}))
        return next(self.responses)


class Retriever:
    def __init__(self, batches):
        self.batches = iter(batches)
        self.requests = []

    def search(self, query, **kwargs):
        self.requests.append({"query": query, **kwargs})
        return {"results": next(self.batches)}


class AgentRuntimeTests(unittest.TestCase):
    def test_search_then_answer_with_actual_context_citation(self):
        client = Client([completion("search_documents", {"query": "Alpha"}),
                         completion("submit_answer", {"answer": "Alpha là một ví dụ. [a]", "citations": ["a"]})])
        retriever = Retriever([[document()]])
        result = run_agent(QUERY, client, retriever, CONFIG)
        self.assertEqual(result["status"], "answered")
        self.assertEqual(result["citations"], ["a"])
        self.assertEqual(result["semantic_review_status"], "pending")
        self.assertEqual(retriever.requests[0]["filters"], QUERY["filter"])
        sent = json.dumps(client.requests, ensure_ascii=False)
        self.assertNotIn("expected_answer", sent)
        self.assertNotIn("answerable", sent)
        self.assertEqual(client.requests[0]["choice"]["function"]["name"], "search_documents")

    def test_model_can_abstain_after_empty_search(self):
        client = Client([completion("search_documents", {"query": "Alpha"}),
                         completion("abstain", {"reason": "Chưa có thông tin cần thiết."})])
        result = run_agent(QUERY, client, Retriever([[]]), CONFIG)
        self.assertEqual(result["status"], "abstain")
        self.assertEqual(result["citations"], [])
        self.assertEqual(result["search_count"], 1)

    def test_invented_or_unlisted_citation_is_error_not_abstention(self):
        for answer, ids in (("Ví dụ. [unknown]", ["unknown"]), ("Ví dụ. [a] [unknown]", ["a"])):
            client = Client([completion("search_documents", {"query": "Alpha"}),
                             completion("submit_answer", {"answer": answer, "citations": ids})])
            result = run_agent(QUERY, client, Retriever([[document()]]), CONFIG)
            self.assertEqual(result["status"], "error")
            self.assertEqual(result["error_type"], "AgentProtocolError")

    def test_old_context_is_not_retained_outside_budget(self):
        config = {**CONFIG, "context_budget_chars": 350}
        old, new = document("a", "OLD_SOURCE_" + "a" * 180), document("b", "NEW_SOURCE_" + "b" * 180)
        client = Client([completion("search_documents", {"query": "first"}),
                         completion("search_documents", {"query": "second"}),
                         completion("submit_answer", {"answer": "Ví dụ cũ. [a]", "citations": ["a"]})])
        result = run_agent(QUERY, client, Retriever([[old], [new]]), config)
        self.assertEqual(result["status"], "error")
        latest = client.requests[-1]["messages"]
        self.assertEqual(sum(message["role"] == "tool" for message in latest), 1)
        self.assertNotIn("OLD_SOURCE_", json.dumps(latest))
        self.assertEqual(result["context_ids"], ["b"])
        self.assertLessEqual(len(result["context"]), 350)

    def test_search_tool_removed_at_limit(self):
        config = {**CONFIG, "max_searches": 1, "max_model_calls": 2}
        client = Client([completion("search_documents", {"query": "first"}),
                         completion("search_documents", {"query": "second"})])
        retriever = Retriever([[document()]])
        result = run_agent(QUERY, client, retriever, config)
        self.assertEqual(result["status"], "error")
        self.assertEqual(len(retriever.requests), 1)
        self.assertNotIn("search_documents", [tool["function"]["name"] for tool in client.requests[-1]["tools"]])
        self.assertEqual(client.requests[-1]["choice"]["function"]["name"], "finish_response")

    def test_search_limit_forces_final_tool_and_preserves_answer_choice(self):
        config = {**CONFIG, "max_searches": 1, "max_model_calls": 2}
        client = Client([completion("search_documents", {"query": "Alpha"}),
                         completion("finish_response", {"decision": "answer", "answer": "Ví dụ. [a]",
                                                        "citations": ["a"], "reason": ""})])
        result = run_agent(QUERY, client, Retriever([[document()]]), config)
        self.assertEqual(result["status"], "answered")
        self.assertEqual(result["search_count"], 1)
        self.assertEqual(result["model_call_count"], 2)
        self.assertEqual([entry["function"]["name"] for entry in client.requests[-1]["tools"]], ["finish_response"])
        self.assertEqual(result["events"][-1]["tool"], "finish_response")
        self.assertEqual(result["context_ids"], ["a"])

    def test_search_limit_can_finish_with_model_abstention(self):
        config = {**CONFIG, "max_searches": 1, "max_model_calls": 2}
        client = Client([completion("search_documents", {"query": "Alpha"}),
                         completion("finish_response", {"decision": "abstain", "answer": "",
                                                        "citations": [], "reason": "Chưa đủ bằng chứng."})])
        result = run_agent(QUERY, client, Retriever([[]]), config)
        self.assertEqual(result["status"], "abstain")
        self.assertEqual(result["abstention_reason"], "Chưa đủ bằng chứng.")
        self.assertEqual(result["citations"], [])

    def test_final_tool_still_rejects_invented_citation(self):
        config = {**CONFIG, "max_searches": 1, "max_model_calls": 2}
        client = Client([completion("search_documents", {"query": "Alpha"}),
                         completion("finish_response", {"decision": "answer", "answer": "Ví dụ. [unknown]",
                                                        "citations": ["unknown"], "reason": ""})])
        result = run_agent(QUERY, client, Retriever([[document()]]), config)
        self.assertEqual(result["status"], "error")
        self.assertIn("Citation", result["error"])

    def test_final_tool_rejects_answer_disguised_as_abstention(self):
        config = {**CONFIG, "max_searches": 1, "max_model_calls": 2}
        client = Client([completion("search_documents", {"query": "Alpha"}),
                         completion("finish_response", {"decision": "abstain", "answer": "Suy đoán đáp án.",
                                                        "citations": [], "reason": "Không đủ bằng chứng."})])
        result = run_agent(QUERY, client, Retriever([[]]), config)
        self.assertEqual(result["status"], "error")

    def test_retrieval_failure_keeps_tool_call_and_error(self):
        client = Client([completion("search_documents", {"query": "Alpha"})])
        retriever = SimpleNamespace(search=Mock(side_effect=RuntimeError("database unavailable")))
        result = run_agent(QUERY, client, retriever, CONFIG)
        self.assertEqual(result["status"], "error")
        searches = [event for event in result["events"] if event["event"] == "search"]
        self.assertEqual(searches[0]["status"], "error")
        self.assertEqual(searches[0]["arguments"], {"query": "Alpha"})

    def test_unknown_tool_is_rejected(self):
        client = Client([completion("run_shell", {"command": "anything"})])
        retriever = Retriever([])
        result = run_agent(QUERY, client, retriever, CONFIG)
        self.assertEqual(result["status"], "error")
        self.assertEqual(retriever.requests, [])

    def test_query_with_gold_is_rejected_before_model_call(self):
        client = Client([])
        with self.assertRaises(ValueError):
            run_agent({**QUERY, "gold": []}, client, Retriever([]), CONFIG)
        self.assertEqual(client.requests, [])


class DeepSeekClientTests(unittest.TestCase):
    def test_installed_sdk_serializes_tools_and_reads_deepseek_usage(self):
        import httpx
        from openai import OpenAI

        def respond(request):
            payload = json.loads(request.content)
            self.assertEqual(payload["thinking"], {"type": "disabled"})
            self.assertEqual(payload["tool_choice"]["function"]["name"], "search_documents")
            return httpx.Response(200, json={
                "id": "unit-test-response", "object": "chat.completion", "created": 1,
                "model": "deepseek-flash", "system_fingerprint": "unit-test-only",
                "choices": [{"index": 0, "finish_reason": "tool_calls", "message": {
                    "role": "assistant", "content": None,
                    "tool_calls": [{"id": "call_1", "type": "function", "function": {
                        "name": "search_documents", "arguments": '{"query":"Alpha"}'}}]}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120,
                          "prompt_cache_hit_tokens": 10, "prompt_cache_miss_tokens": 90},
            })

        client = DeepSeekClient.__new__(DeepSeekClient)
        client.config = CONFIG
        client.api_requests = 0
        client.estimated_cost_upper_usd = 0
        client.client = OpenAI(api_key="unit-test-not-a-real-key", base_url=CONFIG["base_url"],
                               max_retries=0, http_client=httpx.Client(transport=httpx.MockTransport(respond)))
        try:
            from src.agent import SEARCH_TOOL
            result = client.complete([{"role": "user", "content": "Alpha?"}], [SEARCH_TOOL],
                                     {"type": "function", "function": {"name": "search_documents"}})
            self.assertEqual(result["usage"]["prompt_cache_hit_tokens"], 10)
            self.assertEqual(result["message"]["tool_calls"][0]["function"]["name"], "search_documents")
            self.assertNotIn("reasoning_content", result["message"])
            self.assertAlmostEqual(result["estimated_cost_upper_usd"], (10 * 0.006 + 90 * 0.3 + 20 * 1.2) / 1e6)
        finally:
            client.close()

    def test_cached_and_uncached_token_cost(self):
        usage = {"prompt_tokens": 100, "completion_tokens": 20,
                 "prompt_cache_hit_tokens": 10, "prompt_cache_miss_tokens": 90}
        self.assertAlmostEqual(usage_cost_upper(usage, CONFIG["pricing"]), (10 * 0.006 + 90 * 0.3 + 20 * 1.2) / 1e6)
        with self.assertRaises(ProviderCallError):
            usage_cost_upper({}, CONFIG["pricing"])

    def test_cost_limit_stops_before_http_request(self):
        client = DeepSeekClient.__new__(DeepSeekClient)
        client.config = {**CONFIG, "estimated_cost_limit_usd": 1e-12}
        client.api_requests = 0
        client.estimated_cost_upper_usd = 0
        create = Mock()
        client.client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        with self.assertRaises(CostLimitError):
            client.complete([{"role": "user", "content": "question"}], [], "required")
        create.assert_not_called()
        self.assertEqual(client.api_requests, 0)

    def test_provider_error_does_not_expose_api_error_body(self):
        client = DeepSeekClient.__new__(DeepSeekClient)
        client.config = CONFIG
        client.api_requests = 0
        client.estimated_cost_upper_usd = 0
        create = Mock(side_effect=RuntimeError("sensitive-header-value"))
        client.client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        with self.assertRaises(ProviderCallError) as caught:
            client.complete([{"role": "user", "content": "question"}], [], "required")
        self.assertNotIn("sensitive-header-value", str(caught.exception))
        self.assertEqual(client.api_requests, 1)
        self.assertGreater(client.estimated_cost_upper_usd, 0)

    def test_provider_config_rejects_unknown_endpoint(self):
        validate_config(CONFIG)
        with self.assertRaises(ValueError):
            validate_config({**CONFIG, "base_url": "https://example.org"})


if __name__ == "__main__":
    unittest.main()
