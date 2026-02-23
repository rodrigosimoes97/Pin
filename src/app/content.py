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
title,slug,meta_description,html,image_query,pin_title,pin_description,alt_text,tag,faq
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
- natural, human tone; clear US English; avoid medical promises and hype.
- prioritize practical advice over theory; avoid generic filler phrases.
- include at least one concrete real-life example.
- include one short actionable checklist.
- include one "common mistakes" section when relevant.
- structure: strong hook in introduction, scannable H2/H3 sections, short paragraphs, practical takeaways, FAQ, closing encouragement.
- include exactly 5 internal link placeholders in body: href="#recent-1", href="#recent-2", href="#recent-3", href="#recent-4", href="#recent-5".
- include sentence: Educational only — not medical advice.
- if mode=offer include soft recommendation and exact sentence:
  Disclosure: This page may contain affiliate links.
- if mode=info do not include affiliate links.
- faq must be an array of objects using this shape: [{{"question":"...","answer":"..."}}]. Keep answers concise.
- If tag is recipes, include an additional key "recipe" using this exact shape:
  {{
    "prep_time_minutes": 10,
    "cook_time_minutes": 20,
    "total_time_minutes": 30,
    "servings": "4 servings",
    "calories_per_serving": "220 calories",
    "ingredients": ["..."],
    "instructions": ["..."],
    "tips": ["..."],
    "storage": "..."
  }}
- Recipe safety rules when tag=recipes:
  - Use realistic US kitchen ingredient units (cups, tbsp, oz) and practical preparation steps.
  - Keep ingredients realistic, avoid risky techniques, and avoid medical promises.
  - html must include anchors and sections: <h2 id="recipe">Recipe</h2>, <h3 id="ingredients">Ingredients</h3> with <ul>, and <h3 id="instructions">Instructions</h3> with <ol>.
  - Include a tips section and storage guidance in html (<h3 id="tips">Tips</h3>, <h3 id="storage">Storage</h3>) unless genuinely not applicable.
- If tag is not recipes, omit recipe or set recipe to null.
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
) -> dict[str, Any]:
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

    payload["faq"] = _normalize_faq(payload.get("faq"))
    payload["recipe"] = _normalize_recipe(payload.get("recipe"), payload["tag"])

    return payload


def _normalize_faq(raw: Any) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        return []
    items: list[dict[str, str]] = []
    for item in raw[:8]:
        if not isinstance(item, dict):
            continue
        question = str(item.get("question", "")).strip()
        answer = str(item.get("answer", "")).strip()
        if question and answer:
            items.append({"question": question, "answer": answer})
    return items


def _clean_slug(raw: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in raw)
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned.strip("-")[:80]


def _normalize_recipe(raw: Any, tag: str) -> dict[str, Any] | None:
    if tag != "recipes":
        return None
    if not isinstance(raw, dict):
        raise ValueError("Missing or invalid recipe data for recipes tag")

    prep = _coerce_positive_int(raw.get("prep_time_minutes"), "prep_time_minutes")
    cook = _coerce_positive_int(raw.get("cook_time_minutes"), "cook_time_minutes")
    total = _coerce_positive_int(raw.get("total_time_minutes"), "total_time_minutes")
    servings = str(raw.get("servings", "")).strip()
    if not servings:
        raise ValueError("Missing or invalid recipe field: servings")

    calories = str(raw.get("calories_per_serving", "")).strip()
    ingredients = _normalize_recipe_list(raw.get("ingredients"), "ingredients", 25)
    instructions = _normalize_recipe_list(raw.get("instructions"), "instructions", 20)
    tips = _normalize_recipe_list(raw.get("tips"), "tips", 10, required=False)
    storage = str(raw.get("storage", "")).strip()

    if total < prep + cook:
        total = prep + cook

    return {
        "prep_time_minutes": prep,
        "cook_time_minutes": cook,
        "total_time_minutes": total,
        "servings": servings,
        "calories_per_serving": calories,
        "ingredients": ingredients,
        "instructions": instructions,
        "tips": tips,
        "storage": storage,
    }


def _normalize_recipe_list(raw: Any, field: str, limit: int, required: bool = True) -> list[str]:
    if raw is None:
        if required:
            raise ValueError(f"Missing or invalid recipe field: {field}")
        return []
    if not isinstance(raw, list):
        raise ValueError(f"Missing or invalid recipe field: {field}")
    cleaned: list[str] = []
    for item in raw[:limit]:
        value = str(item).strip()
        if value:
            cleaned.append(value)
    if required and not cleaned:
        raise ValueError(f"Missing or invalid recipe field: {field}")
    return cleaned


def _coerce_positive_int(value: Any, field: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Missing or invalid recipe field: {field}") from exc
    if parsed <= 0:
        raise ValueError(f"Missing or invalid recipe field: {field}")
    return min(parsed, 24 * 60)
