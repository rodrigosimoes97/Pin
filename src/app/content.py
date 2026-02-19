from __future__ import annotations

import json
from typing import Any, Dict, Optional

import requests

from .topics import slugify


def _prompt(mode: str, topic: dict, offer: Optional[dict]) -> str:
    offer_text = ""
    if mode == "offer" and offer:
        offer_text = (
            "Offer details for a soft CTA section: "
            f"name={offer['name']}, link={offer['link']}, tags={','.join(offer['tags'])}."
        )

    return f"""
You are writing a US health and wellness article in strict JSON.
Topic: {topic['topic']}
Mode: {mode}
{offer_text}

Return strict JSON object only with keys:
- title
- slug
- html
- image_query
- pin_title
- pin_description
- alt_text

Rules:
- 1200-1600 words of HTML body content.
- Use scannable headings (<h2>, <h3>) and short paragraphs.
- Include section "Educational only — not medical advice." exactly once.
- Include a 14-day plan with Day 1 through Day 14, each day containing:
  - one food task
  - one habit/prep task
  - one tracking task
- Include grocery list section.
- Include meal templates section.
- Include exactly 6 FAQs.
- No medical promises, no mention of curing/treating diseases.
- Do not fabricate or cite specific studies.
- Keep tone practical and compliant for US audience.
- For mode=offer: include one gentle CTA paragraph referencing the provided offer and include this exact sentence once:
  "Disclosure: This page may contain affiliate links."
- For mode=info: do not include any links and do not include disclosure sentence.
- Slug must be deterministic and URL-safe for this topic, based on '{slugify(topic['topic'])}' and mode.
- image_query must be a short phrase for stock photo search.
- pin_title <= 100 chars, pin_description <= 500 chars.
- alt_text should describe the Pinterest image accessibly.

JSON only. No markdown fences.
""".strip()


def generate_post_json(
    openai_api_key: str,
    model: str,
    mode: str,
    topic: dict,
    offer: Optional[dict],
) -> Dict[str, Any]:
    payload = {
        "model": model,
        "input": [
            {
                "role": "user",
                "content": [{"type": "input_text", "text": _prompt(mode, topic, offer)}],
            }
        ],
        "text": {"format": {"type": "json_object"}},
    }
    response = requests.post(
        "https://api.openai.com/v1/responses",
        headers={
            "Authorization": f"Bearer {openai_api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=120,
    )
    response.raise_for_status()
    data = response.json()

    output_text = data.get("output_text")
    if not output_text:
        chunks = []
        for item in data.get("output", []):
            for content in item.get("content", []):
                if content.get("type") in {"output_text", "text"}:
                    chunks.append(content.get("text", ""))
        output_text = "\n".join(chunks).strip()

    post = json.loads(output_text)
    required = {"title", "slug", "html", "image_query", "pin_title", "pin_description", "alt_text"}
    missing = required - set(post.keys())
    if missing:
        raise ValueError(f"Model response missing keys: {sorted(missing)}")
    return post
