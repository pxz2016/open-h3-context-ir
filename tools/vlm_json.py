#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import mimetypes
import re
from pathlib import Path
from typing import Any

from common import ToolError

DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_MODEL = "qwen3-vl-plus"


def _api_key() -> str:
    import os

    key = os.environ.get("DASHSCOPE_API_KEY")
    if not key:
        raise ToolError("missing DASHSCOPE_API_KEY environment variable")
    return key


def _base_url() -> str:
    import os

    return os.environ.get("DASHSCOPE_BASE_URL", DEFAULT_BASE_URL)


def parse_json_object(text: str) -> dict:
    cleaned = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", text.strip(), flags=re.IGNORECASE)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end < start:
        raise ValueError("VLM response does not contain a JSON object")
    payload = json.loads(cleaned[start : end + 1])
    if not isinstance(payload, dict):
        raise ValueError("VLM response root must be an object")
    return payload


def _image_mime_type(path: Path) -> str:
    mime_type, _ = mimetypes.guess_type(path.name)
    if mime_type and mime_type.startswith("image/"):
        return mime_type
    suffix = path.suffix.lower()
    fallback_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
        ".gif": "image/gif",
        ".tif": "image/tiff",
        ".tiff": "image/tiff",
    }
    if suffix in fallback_map:
        return fallback_map[suffix]
    raise ToolError(f"unsupported image format for VLM request: {path}")


def _to_data_url(path: Path) -> str:
    mime_type = _image_mime_type(path)
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise ToolError(f"could not read image for VLM request: {path}") from error
    encoded = base64.b64encode(raw).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def run_vlm_json(model_path: str, images: list[Path], prompt: str, max_new_tokens: int = 2048) -> dict:
    from openai import APIConnectionError, APIStatusError, AuthenticationError, OpenAI

    if not images:
        raise ToolError("at least one image is required for VLM request")
    model_id = model_path or DEFAULT_MODEL
    client = OpenAI(api_key=_api_key(), base_url=_base_url())
    content: list[dict[str, Any]] = [
        {"type": "image_url", "image_url": {"url": _to_data_url(path)}}
        for path in images
    ]
    content.append({"type": "text", "text": prompt})
    try:
        response = client.chat.completions.create(
            model=model_id,
            messages=[{"role": "user", "content": content}],
            temperature=0,
            max_tokens=max_new_tokens,
            stream=False,
        )
    except AuthenticationError as error:
        raise ToolError("DashScope authentication failed for VLM request") from error
    except APIConnectionError as error:
        raise ToolError("DashScope connection failed for VLM request") from error
    except APIStatusError as error:
        raise ToolError(f"DashScope VLM request failed with HTTP {error.status_code}") from error
    except Exception as error:
        raise ToolError("DashScope VLM request failed") from error

    choices = response.choices or []
    if not choices or choices[0].message is None:
        raise ToolError("DashScope VLM response is empty")
    text = choices[0].message.content
    if isinstance(text, list):
        text = "".join(
            item.get("text", "")
            for item in text
            if isinstance(item, dict)
        )
    if not isinstance(text, str) or not text.strip():
        raise ToolError("DashScope VLM response is empty")
    try:
        return parse_json_object(text)
    except ValueError as error:
        raise ToolError(f"DashScope VLM response JSON is invalid: {error}") from error
