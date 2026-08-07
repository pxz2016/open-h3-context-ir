#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import tempfile
from pathlib import Path

from common import ToolError, emit, fail, require_file, run_json
from vlm_json import run_vlm_json


DEFAULT_MODEL = os.environ.get("H3_TEXT_ENCODER_MODEL")
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}

PROMPT = """You are performing evidence extraction, not creative captioning. Return exactly one JSON object and no prose.
Describe only visible evidence. Do not decide what should be retained. Do not infer protected or hidden identity attributes. Preserve all visible text verbatim; use [unclear] for unreadable characters.
Required schema:
{
  "entities": [{
    "entity_id": "E1",
    "category": "person|animal|object|interface|effect|other",
    "identity_hints": [],
    "appearance": {"observations": [], "confidence": "high|medium|low"},
    "clothing": {"observations": [], "confidence": "high|medium|low"},
    "props": {"observations": [], "confidence": "high|medium|low"},
    "action": {"observations": [], "confidence": "high|medium|low"},
    "pose_expression": {"observations": [], "confidence": "high|medium|low"}
  }],
  "environment": {"observations": [], "confidence": "high|medium|low"},
  "lighting": {"observations": [], "confidence": "high|medium|low"},
  "style": {"observations": [], "confidence": "high|medium|low"},
  "layout_text": {"texts_verbatim": [], "layout": [], "confidence": "high|medium|low"},
  "camera": {"framing": [], "viewpoint": [], "motion_evidence": [], "confidence": "high|medium|low"}
}
Empty evidence bundles must be empty arrays, never invented defaults."""


def video_duration(path: Path) -> float:
    payload = run_json(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)])
    return float(payload["format"]["duration"])


def extract_video_frame(path: Path, frame_ms: int | None, output: Path) -> int:
    resolved_ms = frame_ms if frame_ms is not None else round(video_duration(path) * 500)
    completed = subprocess.run([
        "ffmpeg", "-v", "error", "-y", "-ss", f"{resolved_ms / 1000:.6f}",
        "-i", str(path), "-frames:v", "1", str(output),
    ], check=False, capture_output=True, text=True)
    if completed.returncode:
        raise ToolError(completed.stderr.strip() or "could not extract video frame")
    return resolved_ms


def extract(asset: Path, model: str, shot_idx: int | None, frame_ms: int | None) -> dict:
    if asset.suffix.lower() in IMAGE_SUFFIXES:
        evidence = run_vlm_json(model, [asset], PROMPT)
        source = {"asset": str(asset), "shot_idx": shot_idx, "frame_ms": None}
    else:
        with tempfile.TemporaryDirectory(prefix="h3-visual-") as temp_dir:
            frame = Path(temp_dir) / "frame.jpg"
            resolved_ms = extract_video_frame(asset, frame_ms, frame)
            evidence = run_vlm_json(model, [frame], PROMPT)
        source = {"asset": str(asset), "shot_idx": shot_idx, "frame_ms": resolved_ms}
    return {
        "tool": "visual_attributes",
        "status": "ok",
        "source": source,
        **evidence,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="T3: extract independently citable visual attribute bundles.")
    parser.add_argument("asset", nargs="+")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--shot-idx", type=int)
    parser.add_argument("--frame-ms", type=int)
    args = parser.parse_args()
    if not args.model:
        parser.error("--model is required unless H3_TEXT_ENCODER_MODEL is set")
    try:
        results = [
            extract(require_file(asset), args.model, args.shot_idx, args.frame_ms)
            for asset in args.asset
        ]
        emit(results[0] if len(results) == 1 else {
            "tool": "visual_attributes",
            "status": "ok",
            "items": results,
        })
    except (ToolError, OSError, ValueError, ImportError) as error:
        fail(
            "visual_attributes",
            str(error),
            fallback="put the original image/frame in the rewriting context and mark ad-hoc extraction confidence=low",
        )


if __name__ == "__main__":
    main()
