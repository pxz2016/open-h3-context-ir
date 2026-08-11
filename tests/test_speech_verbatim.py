from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import speech_verbatim  # noqa: E402
from common import ToolError  # noqa: E402


def _response(status_code: int, payload):
    response = Mock()
    response.status_code = status_code
    response.json = Mock(return_value=payload)
    return response


class SpeechVerbatimTests(unittest.TestCase):
    def test_transcript_mapping_keeps_millisecond_values(self) -> None:
        with patch.dict(os.environ, {"DASHSCOPE_API_KEY": "test-key"}, clear=False):
            with patch("speech_verbatim.requests.post") as post, patch("speech_verbatim.requests.get") as get:
                post.return_value = _response(200, {"output": {"task_id": "task-1"}})
                get.side_effect = [
                    _response(
                        200,
                        {
                            "output": {
                                "task_status": "SUCCEEDED",
                                "results": [{"transcription_url": "https://example.com/result.json"}],
                            }
                        },
                    ),
                    _response(
                        200,
                        {
                            "results": [
                                {
                                    "transcripts": [
                                        {
                                            "language": "zh",
                                            "sentences": [
                                                {
                                                    "text": "你好 世界",
                                                    "start": 120,
                                                    "end": 980,
                                                    "words": [
                                                        {"word": "你好", "start": 120, "end": 420},
                                                        {"word": "世界", "start": 500, "end": 980},
                                                    ],
                                                }
                                            ],
                                        }
                                    ]
                                }
                            ]
                        },
                    ),
                ]
                payload = speech_verbatim.transcribe(
                    "https://example.com/audio.wav",
                    "qwen3-asr-flash-filetrans",
                    None,
                    "SPEAKER_00",
                    base_url="https://dashscope.aliyuncs.com/api/v1",
                    poll_interval_sec=0.01,
                    timeout_sec=2,
                )
        self.assertEqual(payload["status"], "needs_review")
        segment = payload["segments"][0]
        self.assertEqual(segment["start_ms"], 120)
        self.assertEqual(segment["end_ms"], 980)
        self.assertEqual(segment["words"][0]["start_ms"], 120)
        self.assertEqual(segment["words"][1]["end_ms"], 980)

    def test_local_audio_path_returns_actionable_error(self) -> None:
        with self.assertRaises(ToolError) as ctx:
            speech_verbatim.transcribe(
                str(Path(__file__)),
                "qwen3-asr-flash-filetrans",
                None,
                "SPEAKER_00",
                base_url="https://dashscope.aliyuncs.com/api/v1",
                poll_interval_sec=1,
                timeout_sec=10,
            )
        self.assertIn("upload the file to a public URL", str(ctx.exception))

    def test_polling_failure_status_raises_error(self) -> None:
        with patch("speech_verbatim.requests.get") as get:
            get.return_value = _response(200, {"output": {"task_status": "FAILED", "message": "bad audio"}})
            with self.assertRaises(ToolError) as ctx:
                speech_verbatim._poll_task_until_done(
                    task_id="task-1",
                    base_url="https://dashscope.aliyuncs.com/api/v1",
                    api_key="test-key",
                    poll_interval_sec=0.01,
                    timeout_sec=1,
                )
        self.assertIn("task failed", str(ctx.exception))

    def test_polling_timeout_raises_error(self) -> None:
        with patch("speech_verbatim.requests.get") as get:
            get.return_value = _response(200, {"output": {"task_status": "RUNNING"}})
            with self.assertRaises(ToolError) as ctx:
                speech_verbatim._poll_task_until_done(
                    task_id="task-1",
                    base_url="https://dashscope.aliyuncs.com/api/v1",
                    api_key="test-key",
                    poll_interval_sec=0.01,
                    timeout_sec=0.05,
                )
        self.assertIn("timed out", str(ctx.exception))

    def test_submit_network_error_is_wrapped(self) -> None:
        with patch("speech_verbatim.requests.post", side_effect=requests.RequestException("network")):
            with self.assertRaises(ToolError) as ctx:
                speech_verbatim._submit_transcription_job(
                    audio_url="https://example.com/a.wav",
                    model_id="qwen3-asr-flash-filetrans",
                    language=None,
                    base_url="https://dashscope.aliyuncs.com/api/v1",
                    api_key="test-key",
                    timeout_sec=3,
                )
        self.assertIn("submit request failed", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
