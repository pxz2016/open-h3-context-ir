#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

from common import ToolError, emit, fail, require_file


DEFAULT_MODEL = os.environ.get("H3_ASR_MODEL")
DEFAULT_ALIGNER = os.environ.get("H3_ASR_ALIGNER")


def value(item: Any, name: str, default: Any = None) -> Any:
    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)


def milliseconds(raw: Any) -> int | None:
    if raw is None:
        return None
    return round(float(raw) * 1000)


def transcribe(asset: Path, model_path: str, aligner_path: str, language: str | None, speaker_tag: str) -> dict:
    for variable in ("H3_ASR_DEPS", "H3_SHARED_DEPS", "H3_GRADIO_DEPS"):
        if dependency_path := os.environ.get(variable):
            sys.path.append(dependency_path)
    import torch
    from qwen_asr import Qwen3ASRModel

    model = Qwen3ASRModel.from_pretrained(
        model_path,
        dtype=torch.bfloat16,
        device_map="cuda:0",
        max_inference_batch_size=1,
        max_new_tokens=4096,
        forced_aligner=aligner_path,
        forced_aligner_kwargs={"dtype": torch.bfloat16, "device_map": "cuda:0"},
        local_files_only=True,
    )
    result = model.transcribe(
        audio=str(asset),
        language=language,
        return_time_stamps=True,
    )[0]
    timestamps = value(result, "time_stamps", []) or []
    words = [
        {
            "text": value(item, "text", ""),
            "start_ms": milliseconds(value(item, "start_time")),
            "end_ms": milliseconds(value(item, "end_time")),
            "confidence": "unknown",
        }
        for item in timestamps
    ]
    starts = [item["start_ms"] for item in words if item["start_ms"] is not None]
    ends = [item["end_ms"] for item in words if item["end_ms"] is not None]
    segment = {
        "speaker_tag": speaker_tag,
        "start_ms": min(starts) if starts else 0,
        "end_ms": max(ends) if ends else None,
        "lang": value(result, "language", language or "unknown"),
        "text_verbatim": value(result, "text", ""),
        "words": words,
        "unclear_spans": [],
        "confidence": "low",
    }
    return {
        "tool": "speech_verbatim",
        "status": "needs_review",
        "path": str(asset),
        "segments": [segment],
        "diarization": {"status": "not_run", "speaker_tag_is_assigned": True},
        "verbatim_gate": {
            "approved": False,
            "reason": "Qwen ASR does not expose token confidence. Human review must replace every uncertain span with [unclear] before P2/P5 reuse.",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="T4: Qwen3 ASR transcription with forced-alignment timestamps.")
    parser.add_argument("audio")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--aligner", default=DEFAULT_ALIGNER)
    parser.add_argument("--language")
    parser.add_argument("--speaker-tag", default="SPEAKER_00")
    args = parser.parse_args()
    if not args.model or not args.aligner:
        parser.error("--model and --aligner are required unless H3_ASR_MODEL and H3_ASR_ALIGNER are set")
    try:
        emit(transcribe(require_file(args.audio), args.model, args.aligner, args.language, args.speaker_tag))
    except (ToolError, OSError, ValueError, ImportError, RuntimeError) as error:
        fail(
            "speech_verbatim",
            str(error),
            fallback="forbid dialogue/lyric reuse; audio may only enter through non-verbal music_profile evidence",
        )


if __name__ == "__main__":
    main()
