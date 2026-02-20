from __future__ import annotations

from typing import Any

from .gemini_client import GeminiClient
from .topics import Topic

CONTENT_PROMPT = """Write a US-focused health article.
Return strict JSON object with keys:
slug,title,meta_description,image_query,pin_title,pin_description,alt_text,html
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
- if mode=offer: include soft contextual recommendation and exact disclosure sentence:
  Disclosure: This page may contain affiliate links.
- if mode=info: do not include affiliate links.
- output complete valid HTML fragment in `html` with <h2>, <h3>, <p>, <ul>/<ol>.
"""

payload["slug"] = _clean_slug(payload["slug"])
payload["tag"] = normalize_tag(str(payload.get("tag", ""))) or normalize_tag(topic.tag) or "health"

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

    required = ["slug", "title", "meta_description", "image_query", "pin_title", "pin_description", "alt_text", "html"]
    for key in required:
        if key not in payload or not isinstance(payload[key], str) or not payload[key].strip():
            raise ValueError(f"Missing or invalid article field: {key}")

    payload["slug"] = _clean_slug(payload["slug"])
    if mode == "info":
        payload["html"] = payload["html"].replace("Disclosure: This page may contain affiliate links.", "")
    return payload


def _clean_slug(raw: str) -> str:
    output = "".join(ch.lower() if ch.isalnum() else "-" for ch in raw)
    while "--" in output:
        output = output.replace("--", "-")
    return output.strip("-")[:80]
