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
Return strict JSON object with keys:
slug,title,meta_description,image_query,pin_title,pin_description,alt_text,html,tag
Input:
- topic_name: {topic_name}
- angle: {angle}
- title: {title}
- mode: {mode}
- offer_name: {offer_name}
- offer_link: {offer_link}
Rules:
- informational-first; practical tips readers can apply today.
- natural, human tone. no hype or medical promises.
- structure: intro, H2/H3 sections, practical steps, FAQ, closing encouragement.
- include exactly 3 internal link placeholders with href="#recent-1|2|3" in HTML body.
- include sentence: Educational only — not medical advice.
- choose ONE primary tag from:
  sleep, stress, recipes, home-workouts, gut, weight, anti-inflammatory, longevity, mental-wellness, healthy-habits
- if mode=offer: include soft contextual recommendation and exact disclosure sentence:
  Disclosure: This page may contain affiliate links.
- if mode=info: do not include affiliate links.
- output complete valid HTML fragment in `html` with <h2>, <h3>, <p>, <ul>/<ol>.
"""


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
        ),
        max_output_tokens=3200,
    )

    required = [
        "slug",
        "title",
        "meta_description",
        "image_query",
        "pin_title",
        "pin_description",
        "alt_text",
        "html",
    ]

    for key in required:
        if key not in payload or not isinstance(payload[key], str) or not payload[key].strip():
            raise ValueError(f"Missing or invalid article field: {key}")

    # ✅ normalize slug
    payload["slug"] = _clean_slug(payload.get("slug", title))

    # ✅ normalize tag with safe fallback
    model_tag = str(payload.get("tag", "")).strip().lower()
    topic_tag = str(getattr(topic, "tag", "")).strip().lower()

    normalized = normalize_tag(model_tag)
    if not normalized:
        normalized = normalize_tag(topic_tag)
    if not normalized:
        normalized = "health"

    payload["tag"] = normalized

    # ✅ enforce info mode cleanup
    if mode == "info":
        payload["html"] = payload["html"].replace(
            "Disclosure: This page may contain affiliate links.",
            "",
        )

    return payload


def normalize_tag(raw: str) -> str | None:
    if not raw:
        return None
    tag = raw.strip().lower()
    tag = tag.replace("_", "-")
    tag = tag.replace(" ", "-")
    return tag if tag in ALLOWED_TAGS else None


def _clean_slug(raw: str) -> str:
    output = "".join(ch.lower() if ch.isalnum() else "-" for ch in raw)
    while "--" in output:
        output = output.replace("--", "-")
    return output.strip("-")[:80]
