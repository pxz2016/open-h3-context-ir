from __future__ import annotations

import base64
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import vlm_json  # noqa: E402
from common import ToolError  # noqa: E402


class VlmJsonTests(unittest.TestCase):
    def test_to_data_url_uses_image_mime(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "sample.png"
            image_path.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")
            data_url = vlm_json._to_data_url(image_path)
        self.assertTrue(data_url.startswith("data:image/png;base64,"))
        encoded = data_url.split(",", 1)[1]
        self.assertEqual(base64.b64decode(encoded), b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")

    def test_run_vlm_json_sends_multi_image_chat_request(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            first = Path(temp_dir) / "a.jpg"
            second = Path(temp_dir) / "b.png"
            first.write_bytes(b"\xff\xd8\xff")
            second.write_bytes(b"\x89PNG\r\n\x1a\n")
            captured: dict = {}

            def fake_create(**kwargs):
                captured.update(kwargs)
                return SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok": true}'))]
                )

            fake_client = SimpleNamespace(
                chat=SimpleNamespace(
                    completions=SimpleNamespace(create=fake_create)
                )
            )
            with patch.dict(os.environ, {"DASHSCOPE_API_KEY": "test-key"}, clear=False):
                with patch("openai.OpenAI", return_value=fake_client):
                    result = vlm_json.run_vlm_json(
                        "qwen3-vl-plus", [first, second], "return json", max_new_tokens=64
                    )
        self.assertEqual(result, {"ok": True})
        self.assertEqual(captured["model"], "qwen3-vl-plus")
        self.assertEqual(captured["temperature"], 0)
        self.assertEqual(captured["max_tokens"], 64)
        content = captured["messages"][0]["content"]
        self.assertEqual(content[-1], {"type": "text", "text": "return json"})
        self.assertEqual(content[0]["type"], "image_url")
        self.assertEqual(content[1]["type"], "image_url")
        self.assertTrue(content[0]["image_url"]["url"].startswith("data:image/jpeg;base64,"))
        self.assertTrue(content[1]["image_url"]["url"].startswith("data:image/png;base64,"))

    def test_missing_api_key_raises_clear_error(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ToolError) as ctx:
                vlm_json.run_vlm_json("qwen3-vl-plus", [Path(__file__)], "x")
        self.assertIn("missing DASHSCOPE_API_KEY", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
