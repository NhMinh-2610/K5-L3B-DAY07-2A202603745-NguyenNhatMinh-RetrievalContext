import json
import unittest
from pathlib import Path
from unittest.mock import patch

from src.deepseek_client import DeepSeekClient
from src.vision_client import VisionClient


class VisionBoundaryTests(unittest.TestCase):
    def test_images_come_only_from_retrieved_pages_and_are_limited(self):
        root=Path(__file__).resolve().parents[1]
        config=json.loads((root/"config/agent.json").read_text("utf-8"))
        chunks=[{"id":str(i),"page":page} for i,page in enumerate((5,2,5,6,9))]
        messages=[{"role":"user","content":"Question only"},
                  {"role":"tool","tool_call_id":"call","content":json.dumps({"context_ids":["0","1","2","3","4"],"context":"Evidence"})}]
        with patch.object(DeepSeekClient,"complete",return_value={"model":"mock"}) as complete,patch("fitz.open") as pdf:
            pdf.return_value.__enter__.return_value.__getitem__.return_value.get_pixmap.return_value.tobytes.return_value=b"mock-jpeg"
            client=VisionClient(config,"unit-test-key",chunks,Path("local-data"))
            try:result=client.complete(messages,[],"required")
            finally:client.close()
        self.assertEqual([r["page"] for r in result["image_inputs"]],[5,2,6])
        actual=complete.call_args.args[0]
        self.assertEqual(actual[0],messages[0])
        self.assertEqual(sum(block["type"]=="image_url" for block in actual[1]["content"]),3)
        self.assertIsInstance(messages[1]["content"],str)
