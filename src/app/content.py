from __future__ import annotations

import hashlib
import re
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

    cleaned_slug = _clean_slug(payload["slug"])
    final_tag = normalize_tag(str(payload.get("tag", ""))) or normalize_tag(topic.tag) or "health"
    payload["slug"] = cleaned_slug
    payload["tag"] = final_tag
    payload["pin_title"] = _build_pin_title(payload["title"], cleaned_slug, payload.get("meta_description", ""), final_tag)
    payload["pin_description"] = _build_pin_description(
        payload["title"],
        cleaned_slug,
        final_tag,
        payload.get("meta_description", ""),
        payload.get("html", ""),
    )

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


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _trim_at_word_boundary(text: str, max_chars: int) -> str:
    normalized = _normalize_whitespace(text)
    if len(normalized) <= max_chars:
        return normalized
    trimmed = normalized[: max_chars + 1].rsplit(" ", 1)[0]
    return trimmed if trimmed else normalized[:max_chars].strip()


def _stable_template_index(seed: str, size: int) -> int:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    hashed = int(digest[:8], 16)
    spread = sum(ord(ch) for ch in seed)
    return (hashed + spread) % size


def _extract_first_sentence(html: str) -> str:
    plain = re.sub(r"<[^>]+>", " ", html or "")
    plain = _normalize_whitespace(plain)
    if not plain:
        return ""
    first = re.split(r"(?<=[.!?])\s", plain, maxsplit=1)[0]
    return _trim_at_word_boundary(first, 100)


def _build_pin_title(title: str, slug: str, meta_description: str, tag: str) -> str:
    normalized_title = _normalize_whitespace(title)
    if 40 <= len(normalized_title) <= 70:
        return normalized_title

    keyword = _trim_at_word_boundary(normalized_title, 38)
    benefit_hint = _trim_at_word_boundary(meta_description or f"easy {tag.replace('-', ' ')} plan", 32)
    templates = [
        "Feel Better Faster: {keyword}",
        "A Simpler Way to {keyword}",
        "Build a Better Week With {keyword}",
        "What to Do This Week: {keyword}",
        "Small Changes, Real Results: {keyword}",
        "Your Practical Plan for {keyword}",
    ]
    idx = _stable_template_index(slug or normalized_title, len(templates))
    candidate = templates[idx].format(keyword=keyword.lower())
    if len(candidate) < 40:
        candidate = _normalize_whitespace(f"{candidate}: {benefit_hint}")
    return _trim_at_word_boundary(candidate, 70)


def _build_pin_description(title: str, slug: str, tag: str, meta_description: str, html: str) -> str:
    topic = _trim_at_word_boundary(_normalize_whitespace(title).rstrip(".?!").lower(), 60)
    specificity = ["today", "this week", "5-minute reset", "3-step routine", "next meal", "tomorrow morning"]
    ctas = ["Save this", "Try this today", "Read the full guide"]
    detail_source = _extract_first_sentence(html) or _normalize_whitespace(meta_description)
    detail = _trim_at_word_boundary(detail_source.lower(), 80)
    seed = slug or title

    templates = [
        "Feeling stuck with {topic}? Start with a {specific} approach and use this practical breakdown to keep it realistic, not perfect. {cta}.",
        "If you struggle with {tag}, this {specific} plan gives you clear steps you can use without overhauling your life. {cta}.",
        "Want better momentum with {topic}? Use this {specific} framework to make progress you can actually keep. {cta}.",
        "When your routine feels off, {topic} can feel harder than it should. This guide uses a {specific} strategy with clear examples. {cta}.",
        "You do not need a complete reset for {tag}. This {specific} approach focuses on doable actions and what matters most right now. {cta}.",
        "Question: what would make {topic} easier this week? This guide maps out a {specific} path with practical steps you can use right away. {cta}.",
    ]
    idx = _stable_template_index(seed, len(templates))
    specific = specificity[_stable_template_index(f"{seed}-specific", len(specificity))]
    cta = ctas[_stable_template_index(f"{seed}-cta", len(ctas))]
    template_text = templates[idx].format(topic=topic, tag=tag.replace("-", " "), specific=specific, cta=cta)
    if detail and len(template_text) < 190:
        template_text = f"{template_text[:-1]} based on {detail}."

    description = _trim_at_word_boundary(_normalize_whitespace(template_text), 260)
    if len(description) < 140:
        description = _trim_at_word_boundary(
            f"{description} It is built for real schedules and focuses on one manageable step at a time.",
            260,
        )
    return description


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
