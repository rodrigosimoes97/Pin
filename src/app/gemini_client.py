from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any

import requests

LOG = logging.getLogger(__name__)
API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


@dataclass(frozen=True)
class GeminiClient:
    api_keys: list[str]
    model: str
    timeout_seconds: int = 45

    def generate_json(self, prompt: str, max_output_tokens: int = 1800) -> dict[str, Any]:
        text = self.generate_text(prompt, max_output_tokens=max_output_tokens)
        return parse_json_from_text(text)

    def generate_text(self, prompt: str, max_output_tokens: int = 1800) -> str:
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.6,
                "maxOutputTokens": max_output_tokens,
                "responseMimeType": "application/json",
            },
        }
        errors: list[str] = []
        for attempt in range(2):
            for key_idx, api_key in enumerate(self.api_keys, start=1):
                try:
                    endpoint = f"{API_BASE}/{self.model}:generateContent"
                    response = requests.post(
                        endpoint,
                        params={"key": api_key},
                        json=payload,
                        timeout=self.timeout_seconds,
                    )
                except requests.RequestException as exc:
                    msg = f"key#{key_idx} network_error={type(exc).__name__}"
                    errors.append(msg)
                    LOG.warning("Gemini request failed: %s", msg)
                    continue

                if response.status_code in {429, 500, 502, 503, 504}:
                    msg = f"key#{key_idx} transient_status={response.status_code}"
                    errors.append(msg)
                    LOG.warning("Gemini transient failure; trying next key: %s", msg)
                    continue
                if response.status_code >= 400:
                    msg = f"key#{key_idx} http_error={response.status_code} body={response.text[:160]}"
                    errors.append(msg)
                    LOG.warning("Gemini non-retriable failure: %s", msg)
                    continue

                body = response.json()
                text = _extract_text(body)
                if text:
                    return text
                msg = f"key#{key_idx} empty_response"
                errors.append(msg)

            time.sleep(1.2 * (attempt + 1))
        raise RuntimeError(f"Gemini failed after key failover: {'; '.join(errors)}")


def _extract_text(payload: dict[str, Any]) -> str:
    try:
        candidates = payload.get("candidates", [])
        if not candidates:
            return ""
        parts = candidates[0]["content"]["parts"]
        text = "".join(part.get("text", "") for part in parts)
        return text.strip()
    except (KeyError, TypeError, IndexError):
        return ""


def parse_json_from_text(text: str) -> dict[str, Any]:
    raw = text.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        raw = raw.replace("json\n", "", 1).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        return json.loads(raw[start : end + 1])
