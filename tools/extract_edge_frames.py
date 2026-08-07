#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from common import ToolError, emit, fail, require_file


def run_ffmpeg(arguments: list[str]) -> None:
    completed = subprocess.run(
        ["ffmpeg", "-v", "error", "-y", *arguments],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode:
        raise ToolError(completed.stderr.strip() or "ffmpeg media extraction failed")


def require_audio_stream(video: Path) -> None:
    completed = subprocess.run([
        "ffprobe", "-v", "error",
        "-select_streams", "a:0",
        "-show_entries", "stream=index",
        "-of", "csv=p=0",
        str(video),
    ], check=False, capture_output=True, text=True)
    if completed.returncode:
        raise ToolError(completed.stderr.strip() or "ffprobe failed")
    if not completed.stdout.strip():
        raise ToolError("video has no audio stream")


def output_name(prefix: str | None, suffix: str) -> str:
    return f"{prefix}-{suffix}" if prefix else suffix


def extract_media(video: Path, output_dir: Path, prefix: str | None) -> dict:
    if prefix and (Path(prefix).name != prefix or prefix in {".", ".."}):
        raise ToolError("prefix must be a file-name prefix, not a path")

    output_dir.mkdir(parents=True, exist_ok=True)
    first_output = output_dir / output_name(prefix, "first_frame.png")
    last_output = output_dir / output_name(prefix, "last_frame.png")
    audio_output = output_dir / output_name(prefix, "audio.wav")

    require_audio_stream(video)
    run_ffmpeg([
        "-i", str(video),
        "-map", "0:a:0",
        "-vn",
        "-c:a", "pcm_s16le",
        str(audio_output),
    ])

    run_ffmpeg([
        "-i", str(video),
        "-map", "0:v:0",
        "-frames:v", "1",
        str(first_output),
    ])
    run_ffmpeg([
        "-sseof", "-10",
        "-i", str(video),
        "-map", "0:v:0",
        "-fps_mode", "passthrough",
        "-update", "1",
        str(last_output),
    ])

    return {
        "tool": "extract_edge_frames",
        "status": "ok",
        "video": str(video),
        "first_frame": str(first_output.resolve()),
        "last_frame": str(last_output.resolve()),
        "audio": str(audio_output.resolve()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract the first frame, last frame, and audio track from a video."
    )
    parser.add_argument("video")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument(
        "--prefix",
        help="Output file prefix, for example 'clip-1-14'.",
    )
    args = parser.parse_args()

    try:
        emit(extract_media(
            require_file(args.video),
            Path(args.output_dir).expanduser().resolve(),
            args.prefix,
        ))
    except (ToolError, OSError, ValueError) as error:
        fail("extract_edge_frames", str(error))


if __name__ == "__main__":
    main()
