#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def run_one(request: dict, label: str, prompt: str) -> None:
    output_dir = Path(request["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    command = [
        request["python"],
        request["runner"],
        request["mode"],
        "--model", request["model"],
        "--output", str(output_dir / f"{label}.mp4"),
        "--prompt", prompt,
        "--height", str(request["height"]),
        "--width", str(request["width"]),
        "--frames", str(request["frames"]),
        "--steps", str(request["steps"]),
        "--seed", str(request["seed"]),
        "--attention-backend", request["attention_backend"],
    ]
    for key, option in (("image", "--image"), ("last_image", "--last-image"), ("reference", "--reference")):
        if request.get(key):
            command.extend([option, request[key]])
    subprocess.run(command, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Remote worker for T11 H3-Base blind rendering.")
    parser.add_argument("request")
    args = parser.parse_args()
    request = json.loads(Path(args.request).read_text(encoding="utf-8"))
    run_one(request, "official", request["official_ir"])
    run_one(request, "ours", request["our_ir"])


if __name__ == "__main__":
    main()
