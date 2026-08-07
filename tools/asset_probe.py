#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from common import ToolError, emit, fail, parse_rate, require_file, run_json


def probe(path: Path) -> dict:
    payload = run_json([
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration,format_name:stream=index,codec_type,codec_name,width,height,avg_frame_rate,r_frame_rate,channels,sample_rate,duration",
        "-of",
        "json",
        str(path),
    ])
    streams = payload.get("streams", [])
    video = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
    audio = next((stream for stream in streams if stream.get("codec_type") == "audio"), None)
    suffix = path.suffix.lower()
    if video and suffix in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff"}:
        asset_type = "image"
    elif video:
        asset_type = "video"
    elif audio:
        asset_type = "audio"
    else:
        asset_type = "unknown"

    duration_value = payload.get("format", {}).get("duration")
    if duration_value is None and video:
        duration_value = video.get("duration")
    if duration_value is None and audio:
        duration_value = audio.get("duration")

    return {
        "tool": "asset_probe",
        "status": "ok",
        "path": str(path),
        "type": asset_type,
        "duration_s": round(float(duration_value), 6) if duration_value not in {None, "N/A"} else None,
        "fps": round(parse_rate(video.get("avg_frame_rate") or video.get("r_frame_rate")), 6) if video and parse_rate(video.get("avg_frame_rate") or video.get("r_frame_rate")) is not None else None,
        "resolution": {"width": video.get("width"), "height": video.get("height")} if video else None,
        "has_audio_track": audio is not None,
        "audio_channels": audio.get("channels") if audio else None,
        "sample_rate": int(audio["sample_rate"]) if audio and audio.get("sample_rate") not in {None, "N/A"} else None,
        "streams": [
            {
                "index": stream.get("index"),
                "codec_type": stream.get("codec_type"),
                "codec_name": stream.get("codec_name"),
            }
            for stream in streams
        ],
        "confidence": "high",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="T1: inspect physical media facts with ffprobe.")
    parser.add_argument("asset")
    args = parser.parse_args()
    try:
        emit(probe(require_file(args.asset)))
    except (ToolError, OSError, ValueError) as error:
        fail("asset_probe", str(error), fallback="none; T1 is mandatory")


if __name__ == "__main__":
    main()
