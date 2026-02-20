from __future__ import annotations

from .gemini_client import GeminiClient
from .topics import Topic


TITLE_PROMPT = """You are an SEO editor for US health informational content.
Return JSON only with schema: {{"titles": ["...", "..."]}}.
Create exactly 10 unique titles in US English for topic '{topic_name}' and angle '{angle}'.
Rules:
- high-intent informational keywords for Google US.
- mix: questions, lists, guides, comparisons, benefit statements.
- practical solution or curiosity.
- avoid these phrases: Ultimate Guide, Best Ever.
- no numbering, no bullets, plain title text only.
- each title <= 72 characters.
"""


def generate_titles(client: GeminiClient, topic: Topic) -> list[str]:
    payload = client.generate_json(TITLE_PROMPT.format(topic_name=topic.name, angle=topic.angle), max_output_tokens=700)
    titles = payload.get("titles", [])
    clean = []
    for title in titles:
        if not isinstance(title, str):
            continue
        t = " ".join(title.strip().split())
        if t and "ultimate guide" not in t.lower() and "best ever" not in t.lower():
            clean.append(t)
    if len(clean) < 3:
        raise ValueError("Gemini did not return enough valid titles")
    return clean[:10]


def pick_best_title(titles: list[str]) -> str:
    preferred = sorted(
        titles,
        key=lambda t: (
            -int("?" in t),
            -sum(token in t.lower() for token in ["how", "what", "foods", "tips", "vs"]),
            len(t),
        ),
    )
    return preferred[0]
