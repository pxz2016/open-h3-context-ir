#!/usr/bin/env python3
from __future__ import annotations

import argparse

import librosa
import numpy as np

from common import ToolError, emit, fail, require_file


def profile(path: str) -> dict:
    asset = require_file(path)
    signal, sample_rate = librosa.load(asset, sr=22050, mono=True)
    tempo, beat_frames = librosa.beat.beat_track(y=signal, sr=sample_rate)
    tempo_value = float(np.asarray(tempo).reshape(-1)[0])
    beat_times = librosa.frames_to_time(beat_frames, sr=sample_rate)
    rms = librosa.feature.rms(y=signal)[0]
    centroid = librosa.feature.spectral_centroid(y=signal, sr=sample_rate)[0]
    flatness = librosa.feature.spectral_flatness(y=signal)[0]
    duration = librosa.get_duration(y=signal, sr=sample_rate)
    return {
        "tool": "music_profile",
        "status": "ok",
        "path": str(asset),
        "instrumentation": [],
        "tempo_bpm": round(tempo_value, 3),
        "structure": [{"section": "full_track", "start_ms": 0, "end_ms": round(duration * 1000), "confidence": "low"}],
        "beat_grid_ms": [round(float(value) * 1000) for value in beat_times],
        "dynamics": {
            "rms_mean": round(float(np.mean(rms)), 6),
            "rms_p10": round(float(np.percentile(rms, 10)), 6),
            "rms_p90": round(float(np.percentile(rms, 90)), 6),
        },
        "texture": {
            "spectral_centroid_hz": round(float(np.mean(centroid)), 2),
            "spectral_flatness": round(float(np.mean(flatness)), 6),
        },
        "confidence": {
            "tempo_bpm": "medium",
            "beat_grid_ms": "medium",
            "instrumentation": "low",
            "structure": "low",
        },
        "limitations": "Instrumentation and semantic song sections require an audio-language model and are intentionally left unguessed.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="T6: physical music and beat profile without emotion words.")
    parser.add_argument("audio")
    args = parser.parse_args()
    try:
        emit(profile(args.audio))
    except (ToolError, OSError, ValueError, ImportError) as error:
        fail("music_profile", str(error), fallback="forbid music-beat cuts; use dialogue gaps or action completion points")


if __name__ == "__main__":
    main()
