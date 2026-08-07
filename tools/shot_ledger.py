#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from common import ToolError, emit, fail, require_file


def extract_frame(video: Path, timestamp_s: float, output: Path) -> None:
    completed = subprocess.run([
        "ffmpeg", "-v", "error", "-y", "-ss", f"{timestamp_s:.6f}",
        "-i", str(video), "-frames:v", "1", str(output),
    ], check=False, capture_output=True, text=True)
    if completed.returncode:
        raise ToolError(completed.stderr.strip() or "ffmpeg frame extraction failed")


def build_ledger(video_path: Path, output_dir: Path, threshold: float) -> dict:
    from scenedetect import SceneManager, open_video
    from scenedetect.detectors import ContentDetector

    video = open_video(str(video_path))
    manager = SceneManager()
    manager.add_detector(ContentDetector(threshold=threshold))
    manager.detect_scenes(video, show_progress=False)
    scenes = manager.get_scene_list(start_in_scene=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    ledger = []
    for index, (start, end) in enumerate(scenes, start=1):
        start_s = start.get_seconds()
        end_s = end.get_seconds()
        duration = max(end_s - start_s, 0.001)
        keyframes = []
        for key_index, fraction in enumerate((0.2, 0.5, 0.8), start=1):
            timestamp = start_s + duration * fraction
            output = output_dir / f"shot-{index:03d}-key-{key_index}.jpg"
            extract_frame(video_path, timestamp, output)
            keyframes.append(str(output.resolve()))
        ledger.append({
            "shot_idx": index,
            "start_ms": round(start_s * 1000),
            "end_ms": round(end_s * 1000),
            "keyframes": keyframes,
            "camera_motion_guess": {
                "type": "unknown",
                "amplitude": None,
                "speed": None,
                "confidence": "low",
                "reason": "cut detection does not establish camera motion",
            },
        })
    return {
        "tool": "shot_ledger",
        "status": "ok",
        "path": str(video_path),
        "detector": {"name": "PySceneDetect ContentDetector", "threshold": threshold},
        "shots": ledger,
        "confidence": "high" if scenes else "low",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="T2: detect cuts and extract per-shot keyframes.")
    parser.add_argument("video")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--threshold", type=float, default=27.0)
    args = parser.parse_args()
    try:
        emit(build_ledger(require_file(args.video), Path(args.output_dir).expanduser().resolve(), args.threshold))
    except (ToolError, OSError, ValueError, ImportError) as error:
        fail(
            "shot_ledger",
            str(error),
            fallback="sample uniformly at 2fps and mark all editing timestamps confidence=low",
        )


if __name__ == "__main__":
    main()
