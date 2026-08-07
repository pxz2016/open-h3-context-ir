#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from common import ToolError, emit, fail, read_json, require_file, write_json


def api_json(url: str, token: str, payload: dict | None = None) -> dict:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        url,
        data=body,
        method="POST" if payload is not None else "GET",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise ToolError(f"MiniMax API returned HTTP {error.code}: {detail}") from error


def archive_input(manifest_path: Path, manifest: dict, case_dir: Path) -> dict:
    input_dir = case_dir / "input"
    assets_dir = input_dir / "assets"
    assets_dir.mkdir(parents=True)
    shutil.copy2(manifest_path, input_dir / "request_manifest.json")
    prediction = manifest.get("prediction")
    prediction_file = manifest.get("prediction_file")
    if prediction_file:
        prediction_path = require_file(prediction_file)
        shutil.copy2(prediction_path, case_dir / "expected_verdict.md")
    elif prediction:
        (case_dir / "expected_verdict.md").write_text(str(prediction).rstrip() + "\n", encoding="utf-8")
    else:
        raise ToolError("manifest must contain prediction or prediction_file before the official call")

    request_content = []
    for index, entry in enumerate(manifest.get("content", []), start=1):
        copied = dict(entry)
        local_path = copied.pop("local_path", None)
        if local_path:
            source = require_file(local_path)
            target = assets_dir / f"{index:02d}-{source.name}"
            shutil.copy2(source, target)
        request_content.append(copied)
    if not request_content:
        raise ToolError("manifest content must not be empty")
    return {
        "model": manifest.get("model", "MiniMax-H3"),
        "content": request_content,
        "duration": manifest.get("duration", 5),
        "ratio": manifest.get("ratio", "adaptive"),
    }


def collect(args: argparse.Namespace) -> dict:
    if not args.ack_license_note:
        raise ToolError("read alignment/corpus/LICENSE_NOTE.md and pass --ack-license-note")
    if args.intended_use != "evaluation":
        raise ToolError("official API output training/distillation is blocked by LICENSE_NOTE.md")
    manifest_path = require_file(args.manifest)
    manifest = read_json(manifest_path)
    if manifest.get("rights_basis") not in {"owned_by_requester", "commercially_licensed"}:
        raise ToolError("manifest rights_basis must be owned_by_requester or commercially_licensed")
    if not (manifest.get("prediction") or manifest.get("prediction_file")):
        raise ToolError("manifest must contain prediction or prediction_file before the official call")
    token = os.environ.get(args.token_env)
    if not token:
        raise ToolError(f"missing API token environment variable: {args.token_env}")
    case_dir = Path(args.corpus_root).expanduser().resolve() / args.case_id
    if case_dir.exists():
        raise ToolError(f"case already exists; refusing to overwrite: {case_dir}")
    request_payload = archive_input(manifest_path, manifest, case_dir)
    api_base = args.api_base.rstrip("/")
    submitted = api_json(f"{api_base}/v2/h3_context_ir", token, request_payload)
    task_id = submitted.get("task_id")
    if not task_id:
        write_json(case_dir / "official_response.json", submitted)
        raise ToolError(f"submission response has no task_id: {submitted}")
    deadline = time.monotonic() + args.timeout_seconds
    response = submitted
    while time.monotonic() < deadline:
        response = api_json(f"{api_base}/v2/query/video_generation/{task_id}", token)
        prompt = response.get("task", {}).get("content", {}).get("prompt")
        if prompt:
            break
        status = str(response.get("status") or response.get("task", {}).get("status") or "").lower()
        if status in {"failed", "cancelled", "error"}:
            write_json(case_dir / "official_response.json", response)
            raise ToolError(f"official task ended as {status}")
        time.sleep(args.poll_seconds)
    else:
        write_json(case_dir / "official_response.json", response)
        raise ToolError(f"official task did not finish within {args.timeout_seconds}s")

    official_ir = response["task"]["content"]["prompt"]
    (case_dir / "official_ir.txt").write_text(official_ir.rstrip() + "\n", encoding="utf-8")
    write_json(case_dir / "official_response.json", response)
    write_json(case_dir / "collection_meta.json", {
        "case_id": args.case_id,
        "task_id": task_id,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "api_base": api_base,
        "model": request_payload["model"],
        "usage_tokens": response.get("usage") or response.get("usage_tokens"),
        "blind_status": "official_ir_not_opened_by_tool",
    })
    return {
        "tool": "official_oracle",
        "status": "ok",
        "case_id": args.case_id,
        "task_id": task_id,
        "case_dir": str(case_dir),
        "official_ir_path": str(case_dir / "official_ir.txt"),
        "usage_tokens": response.get("usage") or response.get("usage_tokens"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="T9: collect and archive an official H3-Context-IR case.")
    parser.add_argument("case_id")
    parser.add_argument("manifest")
    parser.add_argument("--corpus-root", default="alignment/corpus")
    parser.add_argument("--api-base", default=os.environ.get("MINIMAX_API_BASE", "https://api.minimax.io"))
    parser.add_argument("--token-env", default="TOKEN")
    parser.add_argument("--poll-seconds", type=float, default=5.0)
    parser.add_argument("--timeout-seconds", type=float, default=900.0)
    parser.add_argument("--intended-use", choices=["evaluation", "training"], default="evaluation")
    parser.add_argument("--ack-license-note", action="store_true")
    args = parser.parse_args()
    try:
        emit(collect(args))
    except (ToolError, OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        fail("official_oracle", str(error), fallback="collect only B-level rendered-video evidence when API use is unavailable")


if __name__ == "__main__":
    main()
