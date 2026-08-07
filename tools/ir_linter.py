#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path

from common import ToolError, emit, fail, require_file


SECTIONS = [
    "subject_definitions",
    "summary",
    "retention_analysis",
    "detailed_description",
    "overall_soundscape",
    "non_diegetic_music",
]
TASK_TYPES = {
    "keyframe completion",
    "reference generation",
    "video editing",
    "video continuation",
    "audio reuse",
    "audio reference",
}
VISIBLE_MARKERS = {"fully_preserved", "partially_preserved", "attribute_transfer", "weak_reference"}
AUDIO_MARKERS = {"fully_copy", "partially_copy", "reference", "weak_reference"}
EMOTION_MUSIC_WORDS = {
    "emotional", "heartwarming", "joyful", "sad", "happy", "nostalgic", "uplifting",
    "romantic", "tense", "dramatic", "comforting", "melancholic", "hopeful", "mysterious",
}


def line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def issue(rule_id: str, guide_ref: str, message: str, *, severity: str = "error", line: int | None = None) -> dict:
    return {"rule_id": rule_id, "guide_ref": guide_ref, "severity": severity, "span": {"line": line}, "message": message}


def parse_sections(text: str) -> tuple[dict[str, str], list[dict]]:
    matches = list(re.finditer(r"(?m)^(subject_definitions|summary|retention_analysis|detailed_description|overall_soundscape|non_diegetic_music):\s*$", text))
    problems = []
    names = [match.group(1) for match in matches]
    if names != SECTIONS:
        problems.append(issue("IR-001", "ref guide 1", f"sections must appear exactly once in order: {', '.join(SECTIONS)}"))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[match.group(1)] = text[match.end() : end].strip()
    return sections, problems


def lint(text: str, duration_s: float | None) -> list[dict]:
    sections, problems = parse_sections(text)
    if any(name not in sections for name in SECTIONS):
        return problems

    definitions = sections["subject_definitions"]
    summary = sections["summary"]
    retention = sections["retention_analysis"]
    detail = sections["detailed_description"]
    soundscape = sections["overall_soundscape"]
    music = sections["non_diegetic_music"]

    defined_labels = re.findall(r"(?m)^(<(?:Subject|Picture|Video|Audio) \d+>)\s", definitions)
    if len(defined_labels) != len(set(defined_labels)):
        problems.append(issue("IR-002", "ref guide 2", "reference labels must be defined once"))
    for family in ("Subject", "Picture", "Video", "Audio"):
        numbers = [int(value) for value in re.findall(rf"<{family} (\d+)>", "\n".join(defined_labels))]
        if numbers and numbers != list(range(1, max(numbers) + 1)):
            problems.append(issue("IR-003", "ref guide 2", f"<{family} N> numbering must be contiguous from 1"))
    used_labels = set(re.findall(r"<(?:Subject|Picture|Video|Audio) \d+>", "\n".join([summary, retention, detail, soundscape, music])))
    undefined = sorted(used_labels - set(defined_labels))
    if undefined:
        problems.append(issue("IR-004", "ref guide 2", f"labels used before definition: {', '.join(undefined)}"))
    missing_retention = sorted(set(defined_labels) - set(re.findall(r"(?m)^(<(?:Subject|Picture|Video|Audio) \d+>)", retention)))
    if missing_retention:
        problems.append(issue("IR-005", "ref guide 4", f"defined labels missing from retention_analysis: {', '.join(missing_retention)}"))

    prefix = re.match(r"^\[([^\]]+)\]", summary)
    task_types: list[str] = []
    if not prefix:
        problems.append(issue("IR-006", "ref guide 3", "summary must begin with a square-bracketed task type"))
    else:
        task_types = prefix.group(1).split(" + ")
        invalid = [item for item in task_types if item not in TASK_TYPES]
        if invalid or len(task_types) != len(set(task_types)):
            problems.append(issue("IR-007", "ref guide 3", "task types must be legal, separated by ' + ', and non-repeating"))
        if "video editing" in task_types and not summary[prefix.end() :].lstrip().startswith("The target video is an edited version of <Video 1>."):
            problems.append(issue("IR-008", "ref guide 3", "video-editing summary must begin with the fixed edited-version sentence"))

    for match in re.finditer(r"(?m)^(<(Subject|Picture|Video) \d+>).*?:\s*([a-z_]+)\s*-", retention):
        if match.group(3) not in VISIBLE_MARKERS:
            problems.append(issue("IR-009", "ref guide 4.1", f"illegal visible retention marker: {match.group(3)}", line=line_number(text, text.find(match.group(0)))))
    for match in re.finditer(r"(?m)^(<Audio \d+>).*?:\s*([a-z_]+)\s*-", retention):
        if match.group(2) not in AUDIO_MARKERS:
            problems.append(issue("IR-010", "ref guide 4.2", f"illegal audio retention marker: {match.group(2)}"))
    if re.search(r"\(S\d+\)", retention):
        problems.append(issue("IR-011", "ref guide 5.4", "speaker IDs are forbidden in retention_analysis"))

    shots = list(re.finditer(r"\[Shot (\d+)\](?: At (\d{2}):(\d{2})\.(\d{3}),)?", detail))
    if not shots:
        problems.append(issue("IR-012", "ref guide 5.1", "detailed_description must contain [Shot 1]"))
    else:
        numbers = [int(match.group(1)) for match in shots]
        if numbers != list(range(1, len(numbers) + 1)):
            problems.append(issue("IR-013", "ref guide 5.1", "shot numbering must be contiguous from 1"))
        if shots[0].group(2) is not None:
            problems.append(issue("IR-014", "ref guide 5.1", "[Shot 1] must not carry a timestamp"))
        timestamps = []
        for match in shots[1:]:
            if match.group(2) is None:
                problems.append(issue("IR-015", "ref guide 5.1", f"[Shot {match.group(1)}] requires At MM:SS.mmm"))
                continue
            milliseconds = (int(match.group(2)) * 60 + int(match.group(3))) * 1000 + int(match.group(4))
            timestamps.append(milliseconds)
        if timestamps != sorted(set(timestamps)):
            problems.append(issue("IR-016", "ref guide 5.1", "shot timestamps must be strictly increasing"))
        if duration_s is not None and any(value >= duration_s * 1000 for value in timestamps):
            problems.append(issue("IR-017", "ref guide 5.1", "shot timestamp must be earlier than target duration"))

    open_dialogue = detail.count("<d>")
    close_dialogue = detail.count("</d>")
    if open_dialogue != close_dialogue:
        problems.append(issue("IR-018", "ref guide 5.4", "dialogue tags must be balanced"))
    dialogues = re.findall(r"<d>\[([^\]]+)\]\s*(.*?)</d>", detail, flags=re.DOTALL)
    if len(dialogues) != open_dialogue:
        problems.append(issue("IR-019", "ref guide 5.4", "every dialogue must begin with a language tag"))
    for language, dialogue in dialogues:
        stripped = dialogue.strip()
        if not language.strip():
            problems.append(issue("IR-020", "ref guide 5.4", "dialogue language must not be empty"))
        if stripped and not re.search(r"[.!?]$", stripped) and "<cutoff>" not in stripped:
            problems.append(issue("IR-021", "ref guide 5.4", "complete dialogue must end with '.', '?', or '!'"))
        if re.search(r"[~•●◆◇★☆😀-🙏]|([!?.,])\1{1,}", stripped):
            problems.append(issue("IR-022", "ref guide 5.4", "dialogue contains decorative punctuation or emoji"))

    speaker_numbers = [int(value) for value in re.findall(r"\(S(\d+)\)", detail)]
    first_seen = []
    for number in speaker_numbers:
        if number not in first_seen:
            first_seen.append(number)
    if first_seen and first_seen != list(range(1, max(first_seen) + 1)):
        problems.append(issue("IR-023", "ref guide 5.4", "speaker IDs must be assigned in first-vocal-event order"))
    for match in re.finditer(r"says in an off-screen voiceover.*?</d>(.{0,160})", detail, flags=re.DOTALL):
        if "lips remain completely closed" not in match.group(1):
            problems.append(issue("IR-024", "base guide 4.4", "off-screen voiceover must be followed by 'lips remain completely closed'"))
    if re.search(r"off[ -]screen voice[ -]over", detail, flags=re.IGNORECASE) and "says in an off-screen voiceover" not in detail:
        problems.append(issue("IR-025", "base guide 4.4", "use the fixed phrase 'says in an off-screen voiceover'"))

    generation = "video editing" not in task_types
    word_count = len(re.findall(r"\b[A-Za-z][A-Za-z'-]*\b", detail))
    if generation and not 350 <= word_count <= 500:
        problems.append(issue("IR-026", "ref guide 5.2", f"generation detailed_description has {word_count} English words; expected 350-500", severity="warning"))
    sentence_count = len([part for part in re.split(r"(?<=[.!?])\s+", soundscape) if part.strip()])
    if soundscape != "N/A" and not 1 <= sentence_count <= 4:
        problems.append(issue("IR-027", "base guide soundscape", "overall_soundscape must contain 1-4 sentences"))
    if "<d>" in soundscape or "<d>" in music:
        problems.append(issue("IR-028", "ref guide 6", "dialogue and lyrics belong only in detailed_description"))
    found_emotions = sorted(word for word in EMOTION_MUSIC_WORDS if re.search(rf"\b{re.escape(word)}\b", music, flags=re.IGNORECASE))
    if found_emotions:
        problems.append(issue(
            "IR-029",
            "base guide 4.7 / case law F-1 conflict",
            f"non_diegetic_music uses mood modifiers found in official IR but forbidden by the guide: {', '.join(found_emotions)}; keep physical instrumentation/tempo/dynamics mandatory",
            severity="warning",
        ))
    if detail.rstrip().endswith(("ing.", "ing", ",")):
        problems.append(issue("IR-030", "phrasebook PH-4", "final action appears to lack a settled held end state", severity="warning"))
    return problems


def main() -> None:
    parser = argparse.ArgumentParser(description="T10: deterministic Context-IR format linter.")
    parser.add_argument("ir")
    parser.add_argument("--duration", type=float)
    args = parser.parse_args()
    try:
        path = require_file(args.ir)
        text = path.read_text(encoding="utf-8")
        problems = lint(text, args.duration)
        emit({"tool": "ir_linter", "status": "ok" if not problems else "violations", "path": str(path), "violations": problems})
    except (ToolError, OSError, ValueError) as error:
        fail("ir_linter", str(error), fallback="run the P6 format checklist manually")


if __name__ == "__main__":
    main()
