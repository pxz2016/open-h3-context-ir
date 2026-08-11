#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import time
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests

from common import ToolError, emit, fail


DEFAULT_MODEL = os.environ.get("DASHSCOPE_ASR_MODEL", "qwen3-asr-flash-filetrans")
DEFAULT_HTTP_BASE_URL = os.environ.get("DASHSCOPE_HTTP_BASE_URL", "https://dashscope.aliyuncs.com/api/v1")
DEFAULT_POLL_INTERVAL_SEC = float(os.environ.get("DASHSCOPE_ASR_POLL_INTERVAL_SEC", "2"))
DEFAULT_TIMEOUT_SEC = float(os.environ.get("DASHSCOPE_ASR_TIMEOUT_SEC", "600"))


def _api_key() -> str:
    key = os.environ.get("DASHSCOPE_API_KEY")
    if not key:
        raise ToolError("missing DASHSCOPE_API_KEY environment variable")
    return key


def _is_http_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _headers(api_key: str, async_mode: bool = False) -> dict[str, str]:
    headers = {
        "Authorization": "Bearer " + api_key,
        "Content-Type": "application/json",
    }
    if async_mode:
        headers["X-DashScope-Async"] = "enable"
    return headers


def _extract_task_id(payload: Any) -> str:
    output = payload.get("output") if isinstance(payload, dict) else None
    task_id = None
    if isinstance(output, dict):
        task_id = output.get("task_id")
    if not task_id and isinstance(payload, dict):
        task_id = payload.get("task_id")
    if not isinstance(task_id, str) or not task_id:
        raise ToolError("DashScope ASR submit response missing task_id")
    return task_id


def _submit_transcription_job(
    *,
    audio_url: str,
    model_id: str,
    language: str | None,
    base_url: str,
    api_key: str,
    timeout_sec: float,
) -> str:
    endpoint = urljoin(base_url.rstrip("/") + "/", "services/audio/asr/transcription")
    body: dict[str, Any] = {
        "model": model_id,
        "input": {"file_url": audio_url},
        "parameters": {"enable_words": True},
    }
    if language:
        body["parameters"]["language_hints"] = [language]
    try:
        response = requests.post(
            endpoint,
            headers=_headers(api_key, async_mode=True),
            json=body,
            timeout=timeout_sec,
        )
    except requests.RequestException as error:
        raise ToolError("DashScope ASR submit request failed") from error
    if response.status_code in {401, 403}:
        raise ToolError("DashScope authentication failed for ASR request")
    if response.status_code >= 400:
        raise ToolError(f"DashScope ASR submit request failed with HTTP {response.status_code}")
    try:
        payload = response.json()
    except ValueError as error:
        raise ToolError("DashScope ASR submit response is not valid JSON") from error
    return _extract_task_id(payload)


def _poll_task_until_done(
    *,
    task_id: str,
    base_url: str,
    api_key: str,
    poll_interval_sec: float,
    timeout_sec: float,
) -> dict[str, Any]:
    endpoint = urljoin(base_url.rstrip("/") + "/", f"tasks/{task_id}")
    deadline = time.monotonic() + timeout_sec
    last_status = "UNKNOWN"
    while time.monotonic() < deadline:
        try:
            response = requests.get(
                endpoint,
                headers=_headers(api_key, async_mode=False),
                timeout=max(5.0, poll_interval_sec * 2),
            )
        except requests.RequestException as error:
            raise ToolError("DashScope ASR task polling failed") from error
        if response.status_code in {401, 403}:
            raise ToolError("DashScope authentication failed for ASR polling")
        if response.status_code >= 400:
            raise ToolError(f"DashScope ASR polling failed with HTTP {response.status_code}")
        try:
            payload = response.json()
        except ValueError as error:
            raise ToolError("DashScope ASR polling response is not valid JSON") from error

        output = payload.get("output") if isinstance(payload, dict) else None
        task_status = payload.get("task_status") if isinstance(payload, dict) else None
        if not task_status and isinstance(output, dict):
            task_status = output.get("task_status")
        if isinstance(task_status, str):
            last_status = task_status
        else:
            last_status = "UNKNOWN"

        normalized = last_status.upper()
        if normalized in {"SUCCEEDED", "SUCCESS"}:
            return payload
        if normalized in {"FAILED", "FAIL", "CANCELED", "CANCELLED"}:
            message = ""
            if isinstance(output, dict):
                message = str(output.get("message") or output.get("error_message") or "")
            raise ToolError(f"DashScope ASR task failed: {message or last_status}")
        time.sleep(max(0.1, poll_interval_sec))
    raise ToolError(f"DashScope ASR task timed out after {timeout_sec:.0f}s (last status: {last_status})")


def _extract_transcription_url(status_payload: dict[str, Any]) -> str:
    output = status_payload.get("output") if isinstance(status_payload, dict) else None
    if not isinstance(output, dict):
        raise ToolError("DashScope ASR task result missing output payload")
    results = output.get("results")
    if isinstance(results, list):
        for item in results:
            if isinstance(item, dict) and isinstance(item.get("transcription_url"), str):
                return item["transcription_url"]
    url = output.get("transcription_url")
    if isinstance(url, str) and url:
        return url
    raise ToolError("DashScope ASR task result missing transcription_url")


def _download_transcription_payload(
    *,
    transcription_url: str,
    api_key: str,
    timeout_sec: float,
) -> dict[str, Any]:
    headers = {"Authorization": "Bearer " + api_key}
    try:
        response = requests.get(transcription_url, headers=headers, timeout=timeout_sec)
    except requests.RequestException as error:
        raise ToolError("DashScope ASR transcription download failed") from error
    if response.status_code in {401, 403}:
        raise ToolError("DashScope authentication failed for transcription download")
    if response.status_code >= 400:
        raise ToolError(f"DashScope ASR transcription download failed with HTTP {response.status_code}")
    try:
        payload = response.json()
    except ValueError as error:
        raise ToolError("DashScope ASR transcription payload is not valid JSON") from error
    if not isinstance(payload, dict):
        raise ToolError("DashScope ASR transcription payload root must be an object")
    return payload


def _millisecond_value(raw: Any) -> int | None:
    if raw is None:
        return None
    try:
        return round(float(raw))
    except (TypeError, ValueError):
        return None


def _sentence_words(sentence: dict[str, Any]) -> list[dict[str, Any]]:
    words_raw = sentence.get("words")
    if not isinstance(words_raw, list):
        return []
    output = []
    for item in words_raw:
        if not isinstance(item, dict):
            continue
        text = item.get("word")
        if not isinstance(text, str):
            text = item.get("text") if isinstance(item.get("text"), str) else ""
        output.append({
            "text": text,
            "start_ms": _millisecond_value(item.get("start")),
            "end_ms": _millisecond_value(item.get("end")),
            "confidence": "unknown",
        })
    return output


def _transcript_segments(payload: dict[str, Any], default_language: str | None, speaker_tag: str) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    results = payload.get("results")
    if not isinstance(results, list):
        return segments
    for result in results:
        if not isinstance(result, dict):
            continue
        transcripts = result.get("transcripts")
        if not isinstance(transcripts, list):
            continue
        for transcript in transcripts:
            if not isinstance(transcript, dict):
                continue
            transcript_lang = transcript.get("language")
            if not isinstance(transcript_lang, str):
                transcript_lang = default_language or "unknown"
            sentences = transcript.get("sentences")
            if not isinstance(sentences, list):
                continue
            for sentence in sentences:
                if not isinstance(sentence, dict):
                    continue
                words = _sentence_words(sentence)
                starts = [item["start_ms"] for item in words if item.get("start_ms") is not None]
                ends = [item["end_ms"] for item in words if item.get("end_ms") is not None]
                start_ms = _millisecond_value(sentence.get("start"))
                end_ms = _millisecond_value(sentence.get("end"))
                segments.append({
                    "speaker_tag": speaker_tag,
                    "start_ms": start_ms if start_ms is not None else (min(starts) if starts else 0),
                    "end_ms": end_ms if end_ms is not None else (max(ends) if ends else None),
                    "lang": transcript_lang,
                    "text_verbatim": sentence.get("text") if isinstance(sentence.get("text"), str) else "",
                    "words": words,
                    "unclear_spans": [],
                    "confidence": "low",
                })
    return segments


def transcribe(
    audio_source: str,
    model_id: str,
    language: str | None,
    speaker_tag: str,
    *,
    base_url: str,
    poll_interval_sec: float,
    timeout_sec: float,
) -> dict[str, Any]:
    if not _is_http_url(audio_source):
        if Path(audio_source).exists():
            raise ToolError(
                "local audio file is not supported by DashScope qwen3-asr-flash-filetrans async API; upload the file to a public URL (for example OSS) and pass that URL"
            )
        raise ToolError("audio input must be an http:// or https:// URL for DashScope async ASR")

    api_key = _api_key()
    task_id = _submit_transcription_job(
        audio_url=audio_source,
        model_id=model_id,
        language=language,
        base_url=base_url,
        api_key=api_key,
        timeout_sec=timeout_sec,
    )
    status_payload = _poll_task_until_done(
        task_id=task_id,
        base_url=base_url,
        api_key=api_key,
        poll_interval_sec=poll_interval_sec,
        timeout_sec=timeout_sec,
    )
    transcription_url = _extract_transcription_url(status_payload)
    result_payload = _download_transcription_payload(
        transcription_url=transcription_url,
        api_key=api_key,
        timeout_sec=timeout_sec,
    )
    segments = _transcript_segments(result_payload, language, speaker_tag)
    return {
        "tool": "speech_verbatim",
        "status": "needs_review",
        "path": audio_source,
        "segments": segments,
        "diarization": {"status": "not_run", "speaker_tag_is_assigned": True},
        "verbatim_gate": {
            "approved": False,
            "reason": "Qwen ASR does not expose reliable token confidence. Human review must replace every uncertain span with [unclear] before P2/P5 reuse.",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="T4: DashScope async Qwen3 ASR transcription with sentence/word timestamps.")
    parser.add_argument("audio", help="Publicly accessible audio URL (http/https)")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="DashScope ASR model ID (default: qwen3-asr-flash-filetrans or DASHSCOPE_ASR_MODEL)")
    parser.add_argument("--aligner", default=os.environ.get("H3_ASR_ALIGNER"), help="deprecated compatibility flag; ignored")
    parser.add_argument("--language")
    parser.add_argument("--speaker-tag", default="SPEAKER_00")
    parser.add_argument("--poll-interval-sec", type=float, default=DEFAULT_POLL_INTERVAL_SEC)
    parser.add_argument("--timeout-sec", type=float, default=DEFAULT_TIMEOUT_SEC)
    parser.add_argument("--base-url", default=DEFAULT_HTTP_BASE_URL, help="DashScope HTTP base URL (default from DASHSCOPE_HTTP_BASE_URL)")
    args = parser.parse_args()

    if args.poll_interval_sec <= 0:
        parser.error("--poll-interval-sec must be > 0")
    if args.timeout_sec <= 0:
        parser.error("--timeout-sec must be > 0")
    try:
        emit(
            transcribe(
                args.audio,
                args.model,
                args.language,
                args.speaker_tag,
                base_url=args.base_url,
                poll_interval_sec=args.poll_interval_sec,
                timeout_sec=args.timeout_sec,
            )
        )
    except (ToolError, OSError, ValueError, RuntimeError) as error:
        fail(
            "speech_verbatim",
            str(error),
            fallback="forbid dialogue/lyric reuse; audio may only enter through non-verbal music_profile evidence",
        )


if __name__ == "__main__":
    main()
