#!/usr/bin/env python3
from __future__ import annotations

import argparse
import itertools
import os
import subprocess
import tempfile
from pathlib import Path

from common import ToolError, emit, fail, read_json, require_file
from vlm_json import DEFAULT_MODEL, run_vlm_json


DEFAULT_MODEL_ID = os.environ.get("DASHSCOPE_VL_MODEL", DEFAULT_MODEL)
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}


def evidence_frame(asset: Path, output: Path) -> Path:
    if asset.suffix.lower() in IMAGE_SUFFIXES:
        return asset
    completed = subprocess.run([
        "ffmpeg", "-v", "error", "-y", "-i", str(asset),
        "-vf", "thumbnail=120", "-frames:v", "1", str(output),
    ], check=False, capture_output=True, text=True)
    if completed.returncode:
        raise ToolError(completed.stderr.strip() or "could not extract binder evidence frame")
    return output


def bind(payload: dict, model: str) -> dict:
    entities = {str(item["entity_id"]): item for item in payload["entities"]}
    pair_ids = payload.get("pairs") or list(itertools.combinations(entities, 2))
    results = []
    with tempfile.TemporaryDirectory(prefix="h3-binder-") as temp_dir:
        temp_root = Path(temp_dir)
        for pair_index, raw_pair in enumerate(pair_ids, start=1):
            left_id, right_id = map(str, raw_pair)
            left = entities[left_id]
            right = entities[right_id]
            left_frame = evidence_frame(require_file(left["asset"]), temp_root / f"{pair_index}-left.jpg")
            right_frame = evidence_frame(require_file(right["asset"]), temp_root / f"{pair_index}-right.jpg")
            prompt = f"""Compare the marked entities in image 1 and image 2 as evidence, not as a creative task.
Image 1 entity: {left_id}; supplied observations: {left.get('attributes', {})}
Image 2 entity: {right_id}; supplied observations: {right.get('attributes', {})}
Return exactly JSON:
{{"same_identity":"true|false|ambiguous","evidence":{{"matching":[],"conflicting":[],"insufficient":[]}},"confidence":"high|medium|low"}}
Use ambiguous whenever occlusion, viewpoint, resolution, or missing identity-bearing features prevents a defensible conclusion. Clothing, pose, scene, and role alone never prove identity."""
            result = run_vlm_json(model, [left_frame, right_frame], prompt, max_new_tokens=768)
            results.append({"entity_pair": [left_id, right_id], **result})
    return {"tool": "cross_asset_binder", "status": "ok", "pairs": results}


def main() -> None:
    parser = argparse.ArgumentParser(description="T8: conservative cross-asset identity binding.")
    parser.add_argument("input", help="JSON containing entities and optional pairs")
    parser.add_argument("--model", default=DEFAULT_MODEL_ID, help="DashScope VLM model ID (default: qwen3-vl-plus or DASHSCOPE_VL_MODEL)")
    args = parser.parse_args()
    try:
        emit(bind(read_json(args.input), args.model))
    except (ToolError, OSError, ValueError, KeyError, ImportError) as error:
        fail(
            "cross_asset_binder",
            str(error),
            fallback="return ambiguous and move the binding decision to P3 with an explicit reason",
        )


if __name__ == "__main__":
    main()
