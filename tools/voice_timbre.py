#!/usr/bin/env python3
from __future__ import annotations

import argparse
import math

import librosa
import numpy as np

from common import ToolError, emit, fail, require_file


def band(value: float, low: float, high: float, labels: tuple[str, str, str]) -> str:
    if value < low:
        return labels[0]
    if value > high:
        return labels[2]
    return labels[1]


def describe(path: str, transcript_words: int | None) -> dict:
    asset = require_file(path)
    signal, sample_rate = librosa.load(asset, sr=16000, mono=True)
    duration = len(signal) / sample_rate if sample_rate else 0.0
    non_silent = librosa.effects.split(signal, top_db=35)
    voiced_seconds = sum((end - start) for start, end in non_silent) / sample_rate
    pitches = librosa.yin(signal, fmin=65, fmax=500, sr=sample_rate)
    pitches = pitches[np.isfinite(pitches)]
    median_pitch = float(np.median(pitches)) if pitches.size else math.nan
    centroid = float(np.mean(librosa.feature.spectral_centroid(y=signal, sr=sample_rate)))
    flatness = float(np.mean(librosa.feature.spectral_flatness(y=signal)))
    rms = librosa.feature.rms(y=signal)[0]
    pace_wpm = (transcript_words / voiced_seconds * 60) if transcript_words and voiced_seconds else None
    return {
        "tool": "voice_timbre",
        "status": "ok",
        "path": str(asset),
        "gender_impression": {"value": "unknown", "confidence": "low"},
        "age_impression": {"value": "unknown", "confidence": "low"},
        "pitch": {
            "value": band(median_pitch, 125, 220, ("low", "mid", "high")) if math.isfinite(median_pitch) else "unknown",
            "median_hz": round(median_pitch, 2) if math.isfinite(median_pitch) else None,
            "confidence": "medium" if pitches.size else "low",
        },
        "pace": {
            "value": band(pace_wpm, 115, 175, ("slow", "measured", "fast")) if pace_wpm else "unknown",
            "words_per_minute": round(pace_wpm, 1) if pace_wpm else None,
            "confidence": "medium" if pace_wpm else "low",
        },
        "texture": {
            "value": band(flatness, 0.02, 0.08, ("tonal", "mixed", "noisy")),
            "spectral_centroid_hz": round(centroid, 2),
            "spectral_flatness": round(flatness, 6),
            "rms_mean": round(float(np.mean(rms)), 6),
            "confidence": "medium",
        },
        "accent": {"value": "unknown", "confidence": "low"},
        "delivery": {
            "value": "continuous" if voiced_seconds / max(duration, 0.001) > 0.7 else "pause-separated",
            "voiced_ratio": round(voiced_seconds / max(duration, 0.001), 4),
            "confidence": "medium",
        },
        "confidence": "low",
        "limitations": "Signal analysis cannot establish gender, age, accent, identity, or emotion.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="T5: conservative signal-based voice profile.")
    parser.add_argument("audio")
    parser.add_argument("--transcript-words", type=int)
    args = parser.parse_args()
    try:
        emit(describe(args.audio, args.transcript_words))
    except (ToolError, OSError, ValueError, ImportError) as error:
        fail("voice_timbre", str(error), fallback="use the most conservative visual inference and mark every field confidence=low")


if __name__ == "__main__":
    main()
