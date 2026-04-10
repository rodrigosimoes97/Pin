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
        # Mandatory delay to avoid 429 Rate Limit
        time.sleep(2.5)

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.6,
                "maxOutputTokens": max_output_tokens,
                "responseMimeType": "application/json",
            },
        }
        errors: list[str] = []
        for attempt in range(3):  # Increased from 2 to 3
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

                if response.status_code == 429:
                    msg = f"key#{key_idx} transient_status=429"
                    errors.append(msg)
                    LOG.warning("Gemini rate limit hit (429); waiting longer before trying next key: %s", msg)
                    time.sleep(5 * (attempt + 1)) # Extra wait for 429
                    continue

                if response.status_code in {500, 502, 503, 504}:
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

            time.sleep(2.0 * (attempt + 1))
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
    # This now handles multiple newlines and preserves structural quotes
    def _fix_newlines(match):
        key_part = match.group(1)
        value_part = match.group(2)
        # Only escape actual newline characters, not already escaped \n
        fixed_value = value_part.replace("\r\n", "\\n").replace("\n", "\\n").replace("\r", "\\n")
        return f'{key_part}"{fixed_value}"'

    # Match "key": "value" where value contains newlines. 
    # Stops at the first quote followed by , or } or ] or end of string
    sanitized = re.sub(r'("(?:\w+)":\s*)"(.*?)"(?=\s*[,}\]])', _fix_newlines, sanitized, flags=re.DOTALL)

    # 6) Try parsing again
    try:
        return json.loads(sanitized)
    except json.JSONDecodeError:
        pass

    # 7) Heuristic fix for unescaped double quotes inside values
    def _repair_quotes(s: str) -> str:
        result = []
        i = 0
        in_string = False
        while i < len(s):
            char = s[i]
            if char == '"':
                # Check if this quote is structural
                is_structural = False
                prev_part = s[max(0, i-20):i] # Increased context
                next_part = s[i+1:i+20]
                
                # Structural cues (more robust):
                # Key start: { " or , "
                if re.search(r'[{\[,]\s*$', prev_part): is_structural = True
                # Key end / Value start: " :
                elif re.match(r'^\s*:', next_part): is_structural = True
                # Value start: : "
                elif re.search(r':\s*$', prev_part): is_structural = True
                # Value end: " , or " } or " ]
                # IMPORTANT: A quote followed by a comma is only structural if 
                # it's NOT in the middle of a sentence (heuristic)
                elif re.match(r'^(\s|\\n|\\r)*[,}\]]', next_part):
                    # Check if it looks like a real end-of-string
                    # Structural if followed by } or ] OR if preceded by something that looks like the end of a field value
                    if re.match(r'^(\s|\\n|\\r)*[}\]]', next_part):
                        is_structural = True
                    # If followed by comma, check if it's "key": "val", pattern
                    elif re.search(r'[:]\s*"[^"]*$', prev_part):
                        is_structural = True
                
                if in_string and not is_structural:
                    # If we are already in a string and this quote doesn't look structural, escape it
                    result.append('\\"')
                else:
                    result.append('"')
                    # Toggle in_string only on structural quotes
                    if is_structural:
                        in_string = not in_string
            else:
                result.append(char)
                # If we see an escaped quote, skip it
                if char == '\\' and i + 1 < len(s) and s[i+1] == '"':
                    result.append('"')
                    i += 1
            i += 1
        return "".join(result)

    # Step 7.1: Pre-process literal newlines to avoid confusing the repair logic
    # but keep them as recognizable tokens
    processing = sanitized.replace("\r\n", "\\n").replace("\n", "\\n").replace("\r", "\\n")
    final_attempt = _repair_quotes(processing)
    
    try:
        return json.loads(final_attempt)
    except json.JSONDecodeError as e:
        # Save failed response for debugging
        try:
            from pathlib import Path
            debug_path = Path("generated/logs/failed_json.txt")
            debug_path.parent.mkdir(parents=True, exist_ok=True)
            debug_path.write_text(text, encoding="utf-8")
            LOG.error("Critical JSON parse failure. Raw response saved to %s", debug_path)
        except Exception:
            pass
            
        LOG.warning("Deep JSON sanitization failed: %s. Raw text snippet: %s", e, text[:200])
        raise e
