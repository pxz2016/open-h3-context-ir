#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys

from common import ToolError, emit, fail, read_json


RATES = {
    "zh": {"unit": "character", "per_second": 4.5, "status": "[HYPOTHESIS: E-2]"},
    "en": {"unit": "word", "per_second": 2.7, "status": "[HYPOTHESIS: E-2]"},
}


def language_key(value: str) -> str:
    normalized = value.strip().lower()
    if normalized.startswith(("zh", "chinese", "mandarin", "cantonese")):
        return "zh"
    return "en"


def unit_count(text: str, language: str) -> int:
    if language == "zh":
        return len(re.findall(r"[\u3400-\u9fff]", text))
    return len(re.findall(r"\b[\w']+\b", text, flags=re.UNICODE))


def calculate(items: list[dict], pause_factor: float) -> dict:
    estimates = []
    raw_total = 0.0
    for item in items:
        language = language_key(str(item.get("lang", "en")))
        text = str(item.get("text", ""))
        count = unit_count(text, language)
        rate = RATES[language]
        estimate = count / rate["per_second"] * 1000
        raw_total += estimate
        estimates.append({
            "lang": item.get("lang", language),
            "text": text,
            "units": count,
            "unit": rate["unit"],
            "rate_per_second": rate["per_second"],
            "rate_status": rate["status"],
            "est_ms": round(estimate),
            "floor_ms": round(estimate * 0.85),
            "ceil_ms": round(estimate * 1.15),
        })
    return {
        "tool": "speech_budget",
        "status": "ok",
        "items": estimates,
        "pause_factor": pause_factor,
        "total_speech_ms": round(raw_total),
        "total_with_pauses_ms": round(raw_total * (1 + pause_factor)),
        "confidence": "low",
        "rule_status": "[HYPOTHESIS: E-2]",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="T7: estimate dialogue duration using explicitly hypothetical language rates.")
    parser.add_argument("input", nargs="?", help="JSON file; stdin when omitted")
    parser.add_argument("--pause-factor", type=float, default=0.2)
    args = parser.parse_args()
    try:
        payload = read_json(args.input) if args.input else json.load(sys.stdin)
        items = payload if isinstance(payload, list) else payload["items"]
        if not 0.15 <= args.pause_factor <= 0.25:
            raise ToolError("pause factor must be between 0.15 and 0.25")
        emit(calculate(items, args.pause_factor))
    except (ToolError, OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        fail("speech_budget", str(error), fallback="none; T7 is mandatory")


if __name__ == "__main__":
    main()
