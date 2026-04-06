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
    raw = _strip_code_fences(text)

    # 1) Tenta carregar direto
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # 2) Tenta extrair o objeto JSON
    try:
        candidate = _extract_first_json_object(raw)
    except json.JSONDecodeError:
        candidate = raw

    # 3) Sanitização profunda
    # Remove caracteres de controle (0-31) exceto tab, newline e carriage return se estiverem escapados
    # Mas aqui simplificamos para remover o que quebra o json.loads
    sanitized = re.sub(r'[\x00-\x1F]+', ' ', candidate)
    
    # Tenta carregar o sanitizado
    try:
        return json.loads(sanitized)
    except json.JSONDecodeError as e:
        LOG.warning("Standard JSON parsing failed: %s. Attempting heuristic fix.", e)
        
        # Heurística para erros comuns de LLM:
        # - Aspas não escapadas dentro de valores de string (muito comum em artigos longos)
        # - Vírgulas faltando entre campos
        
        # Tentativa de escape de aspas internas (heurística agressiva)
        # Procura por "chave": "valor com "aspas" internas"
        # Esta parte é complexa, vamos focar no erro relatado: Expecting ',' delimiter
        # Muitas vezes é uma aspa não escapada que faz o parser achar que a string acabou precocemente.
        
        try:
            # Tenta uma limpeza de quebras de linha que o Gemini às vezes insere erradamente
            sanitized_v2 = sanitized.replace('\n', '\\n').replace('\r', '')
            # Mas não queremos escapar as aspas que delimitam as chaves/valores
            # Então corrigimos as aspas que foram "double-escaped" ou "non-escaped"
            return json.loads(sanitized_v2)
        except:
            raise e
