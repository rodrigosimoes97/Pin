from __future__ import annotations

from typing import Any

from .gemini_client import GeminiClient
from .topics import Topic

ALLOWED_TAGS = {
    "sleep",
    "stress",
    "recipes",
    "home-workouts",
    "gut",
    "weight",
    "anti-inflammatory",
    "longevity",
    "mental-wellness",
    "healthy-habits",
    "health",
}

CONTENT_PROMPT = """Write a US-focused health article.
Return strict JSON object only (no markdown) with keys exactly:
title,slug,meta_description,html,image_query,pin_title,pin_description,alt_text,tag
Input:
- topic_name: {topic_name}
- angle: {angle}
- title: {title}
- mode: {mode}
- offer_name: {offer_name}
- offer_link: {offer_link}
Allowed tag values (lowercase, hyphenated):
{allowed_tags}
Rules:
- informational-first; practical tips readers can apply today.
- natural, human tone; avoid medical promises and hype.
- structure: intro, H2/H3 sections, practical steps, FAQ, closing encouragement.
- include exactly 3 internal link placeholders in body: href="#recent-1", href="#recent-2", href="#recent-3".
- include sentence: Educational only — not medical advice.
- if mode=offer include soft recommendation and exact sentence:
  Disclosure: This page may contain affiliate links.
- if mode=info do not include affiliate links.
"""


def normalize_tag(raw: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in (raw or ""))
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    cleaned = cleaned.strip("-")
    return cleaned if cleaned in ALLOWED_TAGS else ""


def generate_article(
    client: GeminiClient,
    topic: Topic,
    title: str,
    mode: str,
    offer: dict[str, Any] | None,
) -> dict[str, str]:
    payload = client.generate_json(
        CONTENT_PROMPT.format(
            topic_name=topic.name,
            angle=topic.angle,
            title=title,
            mode=mode,
            offer_name=(offer or {}).get("name", ""),
            offer_link=(offer or {}).get("link", ""),
            allowed_tags=", ".join(sorted(ALLOWED_TAGS)),
        ),
        max_output_tokens=3200,
    )

    required = [
        "title",
        "slug",
        "meta_description",
        "html",
        "image_query",
        "pin_title",
        "pin_description",
        "alt_text",
    ]
    for key in required:
        if key not in payload or not isinstance(payload[key], str) or not payload[key].strip():
            raise ValueError(f"Missing or invalid article field: {key}")

    payload["slug"] = _clean_slug(payload["slug"])
    payload["tag"] = normalize_tag(str(payload.get("tag", ""))) or normalize_tag(topic.tag) or "health"

    if mode == "info":
        payload["html"] = payload["html"].replace("Disclosure: This page may contain affiliate links.", "")

    return payload


def _clean_slug(raw: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in raw)
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned.strip("-")[:80]
