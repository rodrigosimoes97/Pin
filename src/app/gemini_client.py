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


def _strip_code_fences(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        # remove a primeira linha ``` ou ```json
        s = s.split("\n", 1)[1] if "\n" in s else ""
        # remove o último ```
        if "```" in s:
            s = s.rsplit("```", 1)[0]
    return s.strip()


def _extract_first_json_object(s: str) -> str:
    start = s.find("{")
    if start == -1:
        raise json.JSONDecodeError("No JSON object found", s, 0)

    depth = 0
    in_str = False
    esc = False

    for i in range(start, len(s)):
        ch = s[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return s[start : i + 1]

    raise json.JSONDecodeError("Unclosed JSON object", s, start)


import re

def parse_json_from_text(text: str) -> dict[str, Any]:
    """
    Parses JSON from text with aggressive sanitization for common LLM errors.
    """
    # 1) Basic cleanup
    raw = _strip_code_fences(text).strip()
    if not raw:
        raise ValueError("Empty response from Gemini")

    # 2) Try standard parsing first
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # 3) Extract first JSON-like object
    try:
        candidate = _extract_first_json_object(raw)
    except json.JSONDecodeError:
        candidate = raw

    # 4) Deep sanitization
    # Remove control characters (0-31) except those that can be escaped
    sanitized = re.sub(r"[\x00-\x1F]+", " ", candidate)

    # 5) Fix unescaped newlines inside string values (very common)
    # This looks for quotes that are followed by a newline but NOT by a comma or closing bracket
    # which usually indicates a newline that should have been escaped as \n
    # We'll use a safer approach: replace actual newlines with literal \n inside what looks like strings
    def _fix_newlines(match):
        return match.group(0).replace("\n", "\\n").replace("\r", "")

    # This regex is a heuristic for string values
    sanitized = re.sub(r'":\s*"[^"]*?\n[^"]*?"', _fix_newlines, sanitized)

    # 6) Try parsing again
    try:
        return json.loads(sanitized)
    except json.JSONDecodeError:
        pass

    # 7) Last resort: heuristic fix for unescaped double quotes inside values
    # This is complex, but we try to escape quotes that aren't preceded by : or preceded by ,
    # and aren't followed by , or } or ]
    # A simpler but often effective fix is to ensure all newlines are escaped
    final_attempt = sanitized.replace("\n", "\\n").replace("\r", "")
    
    # Handle the "Expecting ',' delimiter" error which is almost always unescaped quotes
    # or missing commas between fields.
    try:
        return json.loads(final_attempt)
    except json.JSONDecodeError as e:
        LOG.warning("Deep JSON sanitization failed: %s. Raw text snippet: %s", e, text[:200])
        
        # If we still fail, we try one last trick: 
        # using regex to find and escape double quotes that break the JSON structure.
        try:
            # This regex looks for double quotes that are NOT part of the JSON structure
            # (i.e., not after a brace/bracket/comma and not before a colon/comma/brace/bracket)
            # This is hard to do perfectly, so we use a very conservative approach.
            # For now, let's try to just use the error position to help (if possible)
            # but since we're in a loop, let's just re-raise.
            raise e
        except:
            raise e
