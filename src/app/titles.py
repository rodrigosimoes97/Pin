from __future__ import annotations

import re
from typing import Any

from .gemini_client import GeminiClient
from .topics import Topic


# IMPORTANT:
# We use doubled braces {{ }} so Python .format() does not treat JSON braces as placeholders.
TITLE_PROMPT = """You are a US SEO copywriter for health content.

Generate EXACTLY 10 distinct blog post titles about:
- topic: "{topic_name}"
- angle: "{angle}"

Rules:
- High search intent (informational).
- Mix formats: question, list, how-to, myth-busting, comparison, strong statement.
- Avoid generic clichés like "The Ultimate Guide".
- Human, practical, non-hype tone.
- Titles must be in English.
- Output JSON ONLY in this exact shape:

{{
  "titles": [
    "Title 1",
    "Title 2"
  ]
}}
"""


def _clean_title(s: str) -> str:
    s = (s or "").strip()
    # remove bullets/numbers if model ignores instruction
    s = re.sub(r"^\s*[\-\*\d\.\)\]]\s*", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def generate_titles(client: GeminiClient, topic: Topic, max_output_tokens: int = 700) -> list[str]:
    prompt = TITLE_PROMPT.format(topic_name=topic.name, angle=topic.angle)
    payload: dict[str, Any] = client.generate_json(prompt, max_output_tokens=max_output_tokens)

    titles = payload.get("titles")
    if not isinstance(titles, list):
        raise ValueError("Gemini titles payload missing 'titles' list")

    cleaned: list[str] = []
    seen = set()

    for t in titles:
        if not isinstance(t, str):
            continue
        tt = _clean_title(t)
        if not tt:
            continue
        key = tt.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(tt)

    # Ensure we return at least a few usable titles; if model returns less, pad with safe variants.
    if len(cleaned) < 5:
        base = _clean_title(topic.name) or "Health topic"
        cleaned.extend(
            [
                f"{base}: What to Do First (Simple, Practical Steps)",
                f"Common Mistakes People Make With {base} (And What Helps Instead)",
                f"{base} Explained: What Works, What Doesn't, and Why",
                f"7 Small Changes That Improve {base} This Week",
                f"How to Build a Daily Routine Around {base} Without Overthinking",
            ]
        )

    return cleaned[:10]

def pick_best_title(titles: list[str]) -> str:
    """
    Pick a best candidate title from a list.
    Simple heuristic: prefer titles in a good length range with strong intent words.
    """
    if not titles:
        return "Practical Health Tips You Can Use Today"

    intent_words = {
        "how", "why", "what", "best", "easy", "simple", "steps", "fix", "improve",
        "habits", "routine", "foods", "exercise", "sleep", "stress", "gut"
    }

    scored: list[tuple[int, str]] = []
    for t in titles:
        tt = (t or "").strip()
        if not tt:
            continue

        words = re.findall(r"[a-zA-Z']+", tt.lower())
        length = len(tt)

        score = 0
        # prefer 45–72 chars (often good for SERP)
        if 45 <= length <= 72:
            score += 6
        elif 35 <= length <= 85:
            score += 3

        # add points for intent words presence
        score += sum(1 for w in words if w in intent_words)

        # slight penalty if too long
        if length > 95:
            score -= 3

        scored.append((score, tt))

    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1] if scored else titles[0]
