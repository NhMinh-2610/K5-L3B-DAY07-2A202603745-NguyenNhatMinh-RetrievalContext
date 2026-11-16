"""Kiểm tra ranh giới dữ liệu của giao diện local, không gọi model."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from serve_web import STATIC
from src.web_app import Application, validate_request


class WebTests(unittest.TestCase):
    def test_secret_and_parent_paths_are_not_static_assets(self):
        for path in ("/.env", "/.git/config", "/../.env", "/config/agent.json"):
            self.assertNotIn(path, STATIC)
        self.assertEqual(set(STATIC), {"/", "/app.js", "/style.css"})

    def test_web_does_not_accept_gold_or_api_credentials(self):
        for name in ("gold", "answerable", "expected_answer", "api_key", "base_url"):
            with self.assertRaises(ValueError):
                validate_request({"question": "AI là gì?", name: "unexpected"})

    def test_manual_scope_is_validated_and_model_endpoint_is_not_editable(self):
        validate_request({"question": "BERT là gì?", "configuration": "selected", "filter": {"section": "1.2"}})
        with self.assertRaises(ValueError):
            validate_request({"question": "BERT?", "configuration": "https://example.org"})
        with self.assertRaises(ValueError):
            validate_request({"question": "BERT?", "filter": {"gold_page": 14}})

    def test_dataset_must_be_a_named_local_corpus(self):
        validate_request({"question":"Figure 4.4-3?","dataset":"advanced","configuration":"reference-8"})
        with self.assertRaises(ValueError):
            validate_request({"question":"Read file","dataset":"../../.env"})

    def test_pdf_image_route_rejects_out_of_range_pages_before_reading_file(self):
        for value in (0,357,-1,"../.env"):
            with self.assertRaises(ValueError):
                Application.page_image(None,value)


if __name__ == "__main__":
    unittest.main()
