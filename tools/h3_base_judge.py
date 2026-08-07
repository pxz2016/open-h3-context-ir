#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import secrets
import shlex
import shutil
import subprocess
from pathlib import Path

from common import ToolError, emit, fail, read_json, require_file, write_json


DEFAULT_MODEL = os.environ.get("MINIMAX_H3_MODEL")
DEFAULT_HOST = os.environ.get("H3_JUDGE_HOST")
DEFAULT_REMOTE_PROJECT = os.environ.get("H3_JUDGE_REMOTE_PROJECT")
DEFAULT_REMOTE_OUTPUT = os.environ.get("H3_JUDGE_REMOTE_OUTPUT")
DEFAULT_REMOTE_PYTHON = os.environ.get("H3_JUDGE_REMOTE_PYTHON")
DEFAULT_REMOTE_RUNNER = os.environ.get("H3_JUDGE_REMOTE_RUNNER")


def checked(command: list[str]) -> None:
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.returncode:
        raise ToolError(completed.stderr.strip() or completed.stdout.strip() or f"command failed: {command[0]}")


def prepare(args: argparse.Namespace) -> dict:
    manifest = read_json(args.manifest)
    case_id = str(manifest["case_id"])
    local_dir = Path(args.output_root).expanduser().resolve() / case_id
    if local_dir.exists():
        raise ToolError(f"judge output already exists; refusing to overwrite: {local_dir}")
    staging = local_dir / "staging"
    staging.mkdir(parents=True)
    official_ir = require_file(manifest["official_ir"]).read_text(encoding="utf-8")
    our_ir = require_file(manifest["our_ir"]).read_text(encoding="utf-8")
    remote_dir = f"{args.remote_output.rstrip('/')}/{case_id}"
    remote_request = {
        "mode": manifest.get("mode", "ref2va-video"),
        "model": manifest.get("model") or args.model,
        "python": args.remote_python,
        "runner": args.remote_runner,
        "output_dir": remote_dir,
        "official_ir": official_ir,
        "our_ir": our_ir,
        "height": int(manifest.get("height", 544)),
        "width": int(manifest.get("width", 960)),
        "frames": int(manifest.get("frames", 124)),
        "steps": int(manifest.get("steps", 30)),
        "seed": int(manifest.get("seed", 42)),
        "attention_backend": manifest.get("attention_backend", "flash"),
    }
    for key in ("image", "last_image", "reference"):
        if manifest.get(key):
            source = require_file(manifest[key])
            remote_path = f"{remote_dir}/input-{key}{source.suffix}"
            checked(["ssh", args.host, "mkdir", "-p", remote_dir])
            checked(["scp", str(source), f"{args.host}:{remote_path}"])
            remote_request[key] = remote_path
    request_path = write_json(staging / "judge_request.json", remote_request)
    checked(["ssh", args.host, "mkdir", "-p", remote_dir])
    remote_request_path = f"{remote_dir}/judge_request.json"
    checked(["scp", str(request_path), f"{args.host}:{remote_request_path}"])
    worker = f"{args.remote_project}/tools/h3_base_judge_worker.py"
    checked(["ssh", args.host, f"{shlex.quote(args.remote_python)} {shlex.quote(worker)} {shlex.quote(remote_request_path)}"])
    fetched = local_dir / "source"
    fetched.mkdir()
    checked(["scp", f"{args.host}:{remote_dir}/official.mp4", str(fetched / "official.mp4")])
    checked(["scp", f"{args.host}:{remote_dir}/official.mp4.json", str(fetched / "official.mp4.json")])
    checked(["scp", f"{args.host}:{remote_dir}/ours.mp4", str(fetched / "ours.mp4")])
    checked(["scp", f"{args.host}:{remote_dir}/ours.mp4.json", str(fetched / "ours.mp4.json")])

    swap = bool(secrets.randbits(1))
    mapping = {"A": "ours", "B": "official"} if swap else {"A": "official", "B": "ours"}
    for blind_label, source_label in mapping.items():
        shutil.copy2(fetched / f"{source_label}.mp4", local_dir / f"candidate-{blind_label}.mp4")
    write_json(local_dir / "sealed_mapping.json", mapping)
    evaluation_template = (
        "# Blind H3-Base Evaluation\n\n"
        "Evaluator: \n\n"
        "## Candidate A\n\n"
        "- P1 fidelity red lines achieved: \n"
        "- Artifact counts (mouth/hands/text/end drift): \n"
        "- Narrative rhythm: \n\n"
        "## Candidate B\n\n"
        "- P1 fidelity red lines achieved: \n"
        "- Artifact counts (mouth/hands/text/end drift): \n"
        "- Narrative rhythm: \n\n"
        "Preferred candidate and concrete evidence: \n"
    )
    review_paths = []
    for reviewer in range(1, 4):
        review_path = local_dir / f"blind_evaluation_reviewer_{reviewer}.md"
        review_path.write_text(evaluation_template, encoding="utf-8")
        review_paths.append(str(review_path))
    return {
        "tool": "h3_base_judge",
        "status": "awaiting_three_blind_reviews",
        "case_id": case_id,
        "candidate_a": str(local_dir / "candidate-A.mp4"),
        "candidate_b": str(local_dir / "candidate-B.mp4"),
        "evaluation_sheets": review_paths,
        "mapping": str(local_dir / "sealed_mapping.json"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="T11: render official/our IR through one H3-Base and randomize them for blind review.")
    parser.add_argument("manifest")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--remote-project", default=DEFAULT_REMOTE_PROJECT)
    parser.add_argument("--remote-output", default=DEFAULT_REMOTE_OUTPUT)
    parser.add_argument("--remote-python", default=DEFAULT_REMOTE_PYTHON)
    parser.add_argument("--remote-runner", default=DEFAULT_REMOTE_RUNNER)
    parser.add_argument("--output-root", default="alignment/judgements")
    args = parser.parse_args()
    required = {
        "--host": args.host,
        "--model": args.model,
        "--remote-project": args.remote_project,
        "--remote-output": args.remote_output,
        "--remote-python": args.remote_python,
        "--remote-runner": args.remote_runner,
    }
    missing = [option for option, value in required.items() if not value]
    if missing:
        parser.error(f"missing required configuration: {', '.join(missing)}")
    try:
        emit(prepare(args))
    except (ToolError, OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        fail("h3_base_judge", str(error), fallback="stop at ALIGN section 3 IR-layer comparison and record that T11 was unavailable")


if __name__ == "__main__":
    main()
