import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from run_advanced import pass_result
from src.advanced_agent import run_agent
from src.document_store import references


def response(calls):
    return {"finish_reason":"tool_calls","message":{"role":"assistant","content":None,"tool_calls":[
        {"id":str(i),"type":"function","function":{"name":name,"arguments":json.dumps(args)}}
        for i,(name,args) in enumerate(calls)]}}


class Client:
    def __init__(self,replies):self.replies=iter(replies);self.requests=[]
    def complete(self,messages,tools,tool_choice):
        self.requests.append(messages)
        return next(self.replies)


class Retriever:
    def search(self,query,**kwargs):
        chunk={"id":query,"source_id":"doc","source":"url","page":1,"text":"Evidence "+query,"metadata":{}}
        return {"results":[chunk]}


class AdvancedTests(unittest.TestCase):
    def setUp(self):
        self.query={"id":"q","split":"dev","question":"Compare A and B","filter":{}}
        self.config={"max_model_calls":4,"max_searches":3,"top_k":3,"context_budget_chars":1000,"retrieval_method":"hybrid"}

    def test_native_parallel_search_returns_every_id_and_sends_one_context(self):
        client=Client([response([("search_documents",{"query":"a"}),("search_documents",{"query":"b"})]),
                       response([("submit_answer",{"answer":"A [a]; B [b]","citations":["a","b"]})])])
        trace=run_agent(self.query,client,Retriever(),self.config)
        self.assertEqual(trace["status"],"answered")
        self.assertEqual(trace["search_count"],2)
        results=[json.loads(m["content"]) for m in client.requests[1] if m["role"]=="tool"]
        self.assertEqual(len(results),2)
        self.assertEqual(sum("context" in p for p in results),1)
        self.assertEqual(set(results[-1]["context_ids"]),{"a","b"})

    def test_extra_search_is_rejected_and_not_executed(self):
        client=Client([response([("search_documents",{"query":"a"}),("search_documents",{"query":"b"}),("search_documents",{"query":"c"})]),
                       response([("finish_response",{"decision":"answer","answer":"A [a]","citations":["a"],"reason":""})])])
        trace=run_agent(self.query,client,Retriever(),{**self.config,"max_searches":2})
        self.assertEqual(trace["status"],"answered")
        self.assertEqual(trace["search_count"],2)
        payload=json.loads(client.requests[1][-2]["content"])
        self.assertEqual(payload["error"],"search_budget_exhausted")

    def test_bad_citation_requires_an_actual_corrected_model_response(self):
        client=Client([response([("search_documents",{"query":"a"})]),
                       response([("submit_answer",{"answer":"A [a]","citations":["a","missing"]})]),
                       response([("submit_answer",{"answer":"A [a]","citations":["a"]})])])
        trace=run_agent(self.query,client,Retriever(),self.config)
        self.assertEqual(trace["status"],"answered")
        self.assertEqual(trace["model_call_count"],3)
        self.assertTrue(any(e["event"]=="answer_rejected" for e in trace["events"]))

    def test_multihop_cannot_pass_with_only_one_required_page(self):
        case={"answerable":True,"gold":[{"page":1,"reference":"Figure 1.1-1"},{"page":2,"reference":"Table 2.2-2"}]}
        trace={"status":"answered","citations":["a"]}
        lookup={"a":{"page":1,"metadata":{"reference":"Figure 1.1-1"}}}
        self.assertFalse(pass_result(case,trace,{"answer_grade":2,"citation_support":[True]},lookup))

    def test_reference_anchors_are_explicit_question_identifiers(self):
        self.assertEqual(references("Hình G.4-1 và bảng 4.2-2"),["Figure G.4-1","Table 4.2-2"])
        self.assertEqual(references("What does technology readiness mean?"),[])


if __name__=="__main__":unittest.main()
