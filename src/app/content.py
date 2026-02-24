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


import re

_DUP_WORD_RE = re.compile(r"\b(\w+)(\s+\1\b)+", re.IGNORECASE)
_LEADING_LABEL_RE = re.compile(r"^\s*(question|tip|guide)\s*:\s*", re.IGNORECASE)

def _cleanup_pin_description(text: str, cta: str) -> str:
    # Normalize whitespace first
    text = _normalize_whitespace(text)

    # Remove leading labels like "Question:"
    text = _LEADING_LABEL_RE.sub("", text).strip()

    # Remove "based on ..." artifacts (drop everything after "based on")
    # This prevents broken endings like "Save this based on tired of takeout?."
    lower = text.lower()
    pos = lower.find(" based on ")
    if pos != -1:
        text = text[:pos].rstrip()
        if not text.endswith((".", "?", "!")):
            text += "."

    # Fix duplicated consecutive words: "this this" -> "this"
    while True:
        new = _DUP_WORD_RE.sub(r"\1", text)
        if new == text:
            break
        text = new

    # Normalize weird punctuation
    text = text.replace("?.", "?").replace(".?", "?")
    text = re.sub(r"\.\.+", ".", text)   # ".." -> "."
    text = re.sub(r"\?\?+", "?", text)   # "??" -> "?"
    text = re.sub(r"!!+", "!", text)     # "!!" -> "!"

    # Ensure exactly ONE CTA sentence at end
    cta_clean = cta.strip().rstrip(".!?")
    # Remove any existing CTA variants at end to avoid duplicates
    for variant in ["Save this", "Try this today", "Read the full guide"]:
        variant_clean = variant.strip().rstrip(".!?")
        text = re.sub(rf"\s*{re.escape(variant_clean)}[.!?]\s*$", "", text, flags=re.IGNORECASE).rstrip()

    if not text.endswith((".", "?", "!")):
        text += "."
    text = text.rstrip() + f" {cta_clean}."

    return _normalize_whitespace(text)


def _build_pin_description(title: str, slug: str, tag: str, meta_description: str, html: str) -> str:
    del title
    tag_phrase = tag.replace("-", " ")
    base_topic = _trim_at_word_boundary(_normalize_whitespace(meta_description).lower(), 54)
    if not base_topic:
        base_topic = _trim_at_word_boundary(f"your {tag_phrase} routine", 54)

    # Avoid collisions with templates that already contain "this ..."
    # Use specificity items that won't create "this this ..."
    specificity = ["today", "this week", "a 5-minute reset", "a 3-step routine", "your next meal", "tomorrow morning"]
    ctas = ["Save this", "Try this today", "Read the full guide"]

    seed = slug or meta_description or tag

    templates = [
        "Feeling overwhelmed lately? This {specific} plan helps you simplify {topic} with practical steps you can stick to.",
        "Struggling to stay consistent with {tag}? Try this {specific} approach to make progress without changing everything at once.",
        "Having trouble making {topic} work in real life? Use this {specific} framework to keep things simple and doable.",
        # FIX: removed "this {specific} breakdown" to prevent "this this week"
        "If you cannot seem to keep up with {tag}, this breakdown focuses on realistic actions for busy days {specific}.",
        "When routines feel hard to maintain, {topic} usually needs a simpler plan. Start with this {specific} path and build momentum.",
        "Looking for a practical reset? This {specific} strategy helps you improve {tag} habits with clear, manageable steps.",
    ]

    idx = _stable_template_index(seed, len(templates))
    specific = specificity[_stable_template_index(f"{seed}-specific", len(specificity))]
    cta = ctas[_stable_template_index(f"{seed}-cta", len(ctas))]

    template_text = templates[idx].format(topic=base_topic, tag=tag_phrase, specific=specific, cta=cta)

    # IMPORTANT: do NOT append "based on {detail}" — it creates broken, spammy text.
    # (If you want detail, better incorporate it in future as a clean second sentence.)
    description = _cleanup_pin_description(template_text, cta)

    # Enforce length 140–260 after cleanup
    description = _trim_at_word_boundary(description, 260)

    if len(description) < 140:
        extra = "Built for real schedules with one small step at a time."
        # Insert extra sentence BEFORE CTA
        cta_sentence = f" {cta.strip().rstrip('.!?')}."
        if description.endswith(cta_sentence):
            base = description[: -len(cta_sentence)].rstrip()
            if not base.endswith((".", "?", "!")):
                base += "."
            description = _trim_at_word_boundary(f"{base} {extra} {cta.strip().rstrip('.!?')}.", 260)
        else:
            description = _trim_at_word_boundary(f"{description} {extra}", 260)

        # re-clean to ensure exactly one CTA at end
        description = _cleanup_pin_description(description, cta)
        description = _trim_at_word_boundary(description, 260)

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
