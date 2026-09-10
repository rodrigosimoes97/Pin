from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Any

import requests

LOG = logging.getLogger(__name__)
API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

# Erros permanentes que NÃO devem ser retentados
_PERMANENT_HTTP_ERRORS = {400, 401, 403, 404}

# Máximo de rodadas de retry em erros transitórios
_MAX_ROUNDS = 2

# Backoff base (s) para 5xx
_BACKOFF_5XX_BASE = 5

# Cap de backoff (s) — evita travar o pipeline
_BACKOFF_CAP = 60


@dataclass(frozen=True)
class GeminiClient:
    api_keys: list[str]
    model: str
    timeout_seconds: int = 60

    def generate_json(self, prompt: str, max_output_tokens: int = 3000) -> dict[str, Any]:
        text, finish_reason = self._call(prompt, max_output_tokens=max_output_tokens)
        if finish_reason == "MAX_TOKENS":
            LOG.warning(
                "[Gemini] finishReason=MAX_TOKENS — resposta truncada. "
                "Aumente max_output_tokens ou simplifique o prompt."
            )
            raise ValueError("Gemini truncou a resposta (MAX_TOKENS). JSON incompleto.")
        return parse_json_from_text(text)

    def generate_text(self, prompt: str, max_output_tokens: int = 3000) -> str:
        text, _ = self._call(prompt, max_output_tokens=max_output_tokens)
        return text

    def _call(self, prompt: str, max_output_tokens: int = 3000) -> tuple[str, str]:
        """
        Retorna (text, finishReason).

        Estratégia por tipo de erro:
        - 429: respeita Retry-After; passa para próxima key; backoff acumulado por key
        - 502/503/504/500: backoff exponencial com cap; passa para próxima key
        - 400/401/403/404: erro permanente — passa para próxima key sem espera
        - Timeout/ConnectionError: passa para próxima key imediatamente
        - Entre rodadas: pausa progressiva antes de tentar tudo novamente
        """
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "maxOutputTokens": max_output_tokens,
                "responseMimeType": "application/json",
                "thinkingConfig": {"thinkingLevel": "low"},
            },
        }

        # Modelos para fallback caso o modelo principal esteja com 503 (capacidade esgotada)
        candidate_models = [self.model]
        for fb in ["gemini-2.5-flash", "gemini-1.5-flash", "gemini-2.0-flash"]:
            if fb not in candidate_models:
                candidate_models.append(fb)

        errors: list[str] = []

        for round_idx in range(_MAX_ROUNDS + 1):
            # A cada rodada, se a anterior falhou totalmente, tenta o próximo modelo da lista
            current_model = candidate_models[min(round_idx, len(candidate_models) - 1)]

            for key_idx, api_key in enumerate(self.api_keys, start=1):
                endpoint = f"{API_BASE}/{current_model}:generateContent"
                LOG.info(
                    "[Gemini] modelo=%s key#%d rodada=%d enviando...",
                    current_model,
                    key_idx,
                    round_idx + 1,
                )

                try:
                    response = requests.post(
                        endpoint,
                        params={"key": api_key},
                        json=payload,
                        timeout=self.timeout_seconds,
                    )
                except requests.Timeout:
                    msg = f"key#{key_idx} timeout"
                    errors.append(msg)
                    LOG.warning("[Gemini] %s", msg)
                    continue
                except requests.ConnectionError as exc:
                    msg = f"key#{key_idx} connection_error={type(exc).__name__}"
                    errors.append(msg)
                    LOG.warning("[Gemini] %s", msg)
                    continue
                except requests.RequestException as exc:
                    msg = f"key#{key_idx} request_error={type(exc).__name__}"
                    errors.append(msg)
                    LOG.warning("[Gemini] %s", msg)
                    continue

                status = response.status_code

                # 429 Rate Limit
                # Se ainda há outras keys para tentar nesta rodada, passe imediatamente para a próxima key!
                # Não bloqueie o fluxo por dezenas de segundos se há outras chaves disponíveis.
                if status == 429:
                    retry_wait = min(_parse_retry_after(response) or (10 * (round_idx + 1)), _BACKOFF_CAP)
                    msg = f"key#{key_idx} status=429 (quota/rate limit) retry_delay={retry_wait:.0f}s"
                    errors.append(msg)
                    LOG.warning("[Gemini] %s — alternando para próxima key", msg)
                    # Pequena pausa de 1s para não bombardear conexões
                    time.sleep(1)
                    continue

                # 5xx transitório (503 Service Unavailable / alta demanda)
                if status in {500, 502, 503, 504}:
                    wait = min(_BACKOFF_5XX_BASE * (round_idx + 1), 15)
                    msg = f"key#{key_idx} status={status} (alta demanda no modelo {current_model})"
                    errors.append(msg)
                    LOG.warning("[Gemini] %s — tentando próxima key", msg)
                    time.sleep(wait)
                    continue

                # Erros permanentes — sem espera, sem retry na mesma key
                if status in _PERMANENT_HTTP_ERRORS:
                    body_preview = response.text[:200]
                    msg = f"key#{key_idx} status={status} PERMANENTE body={body_preview}"
                    errors.append(msg)
                    LOG.error("[Gemini] %s", msg)
                    continue

                # Outros erros HTTP
                if status >= 400:
                    body_preview = response.text[:200]
                    msg = f"key#{key_idx} status={status} body={body_preview}"
                    errors.append(msg)
                    LOG.warning("[Gemini] %s", msg)
                    continue

                # Sucesso
                body = response.json()
                text = _extract_text(body)
                finish_reason = _extract_finish_reason(body)

                LOG.info(
                    "[Gemini] modelo=%s key#%d rodada=%d OK finishReason=%s len_chars=%d",
                    current_model,
                    key_idx,
                    round_idx + 1,
                    finish_reason,
                    len(text),
                )

                if text:
                    return text, finish_reason

                msg = f"key#{key_idx} empty_response finishReason={finish_reason}"
                errors.append(msg)
                LOG.warning("[Gemini] %s", msg)

            # Pausa breve entre rodadas completas (quando todas as 4 keys deram erro)
            if round_idx < _MAX_ROUNDS:
                inter_wait = 5 * (round_idx + 1)
                next_model = candidate_models[min(round_idx + 1, len(candidate_models) - 1)]
                LOG.warning(
                    "[Gemini] Todas as keys falharam no modelo %s na rodada %d. "
                    "Aguardando %ds antes de tentar no modelo %s.",
                    current_model,
                    round_idx + 1,
                    inter_wait,
                    next_model,
                )
                time.sleep(inter_wait)

        raise RuntimeError(
            f"Gemini falhou após {_MAX_ROUNDS + 1} rodadas "
            f"com {len(self.api_keys)} key(s). "
            f"Últimos erros: {'; '.join(errors[-6:])}"
        )


# ──────────────────────────────────────────────────────────────
# Helpers internos
# ──────────────────────────────────────────────────────────────

def _parse_retry_after(response: requests.Response) -> float | None:
    """Extrai tempo de espera do Retry-After header ou do corpo JSON."""
    ra = response.headers.get("Retry-After", "")
    if ra:
        try:
            return float(ra)
        except ValueError:
            pass

    try:
        body = response.json()
        details = body.get("error", {}).get("details", [])
        for detail in details:
            delay_str = str(detail.get("retryDelay", ""))
            if delay_str:
                seconds = float(re.sub(r"[^\d.]", "", delay_str) or "0")
                if seconds > 0:
                    return seconds
    except Exception:
        pass

    return None


def _extract_text(payload: dict[str, Any]) -> str:
    try:
        candidates = payload.get("candidates", [])
        if not candidates:
            return ""
        parts = candidates[0]["content"]["parts"]
        return "".join(part.get("text", "") for part in parts).strip()
    except (KeyError, TypeError, IndexError):
        return ""


def _extract_finish_reason(payload: dict[str, Any]) -> str:
    try:
        candidates = payload.get("candidates", [])
        if not candidates:
            return "UNKNOWN"
        return str(candidates[0].get("finishReason", "UNKNOWN"))
    except (KeyError, TypeError, IndexError):
        return "UNKNOWN"


def _strip_code_fences(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else ""
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


def parse_json_from_text(text: str) -> dict[str, Any]:
    """
    Parse JSON do texto com sanitização para erros comuns de LLMs.
    NÃO tenta reparar JSON truncado (MAX_TOKENS é tratado em generate_json).
    """
    raw = _strip_code_fences(text).strip()
    if not raw:
        raise ValueError("Resposta vazia do Gemini")

    # Tentativa direta
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Extrai primeiro objeto JSON
    try:
        candidate = _extract_first_json_object(raw)
    except json.JSONDecodeError:
        candidate = raw

    # Remove chars de controle inválidos em JSON (mantém \t \n \r)
    sanitized = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]+", " ", candidate)

    try:
        return json.loads(sanitized)
    except json.JSONDecodeError:
        pass

    # Escapa newlines literais dentro de valores de string
    def _fix_newlines(match: re.Match) -> str:
        key_part = match.group(1)
        value_part = match.group(2)
        fixed = (
            value_part.replace("\r\n", "\\n").replace("\n", "\\n").replace("\r", "\\n")
        )
        return f'{key_part}"{fixed}"'

    sanitized = re.sub(
        r'("(?:\w+)":\s*)"(.*?)"(?=\s*[,}\]])',
        _fix_newlines,
        sanitized,
        flags=re.DOTALL,
    )

    try:
        return json.loads(sanitized)
    except json.JSONDecodeError as exc:
        try:
            from pathlib import Path

            debug_path = Path("generated/logs/failed_json.txt")
            debug_path.parent.mkdir(parents=True, exist_ok=True)
            debug_path.write_text(text, encoding="utf-8")
            LOG.error("[Gemini] Parse JSON falhou. Salvo em %s", debug_path)
        except Exception:
            pass

        LOG.warning("[Gemini] Parse JSON falhou: %s. Snippet: %.200s", exc, text)
        raise exc
