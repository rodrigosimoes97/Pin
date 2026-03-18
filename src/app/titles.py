from __future__ import annotations

from .gemini_client import GeminiClient
from .topics import Topic


TITLE_PROMPT = """You are an expert SEO editor for a major US health publication.
Return JSON only with schema: {{"titles": ["...", "..."]}}.
Create exactly 10 unique, high-CTR titles in US English for topic '{topic_name}' and angle '{angle}'.

Rules for High-Quality Titles:
- Use power words (e.g., Simple, Effective, Daily, Practical, Science-Backed, Realistic).
- Mix different formats:
  - The "How-To" (e.g., How to Actually [Benefit] Without [Struggle])
  - The "Listicle" (e.g., 5 Practical Ways to [Benefit] Today)
  - The "Question" (e.g., Struggling with [Topic]? Try This 5-Minute Reset)
  - The "Benefit-First" (e.g., Feel More Energized with This Simple [Topic] Routine)
- Target US search intent: informational, looking for quick wins and sustainable habits.
- avoid these phrases: Ultimate Guide, Best Ever, Secrets Revealed, You Won't Believe.
- each title must be between 40 and 70 characters.
- no numbering, no bullets, plain title text only.
"""


import random

def generate_titles(client: GeminiClient, topic: Topic, excluded_titles: list[str] | None = None) -> list[str]:
    excluded_text = ""
    if excluded_titles:
        excluded_text = f"\nAvoid these exact titles: {', '.join(excluded_titles[:10])}"

    payload = client.generate_json(
        TITLE_PROMPT.format(topic_name=topic.name, angle=topic.angle) + excluded_text,
        max_output_tokens=700
    )
    titles = payload.get("titles", [])
    clean = []
    for title in titles:
        if not isinstance(title, str):
            continue
        t = " ".join(title.strip().split())
        if t and "ultimate guide" not in t.lower() and "best ever" not in t.lower():
            if not excluded_titles or t not in excluded_titles:
                clean.append(t)
    if len(clean) < 3:
        # Fallback if too many were excluded
        for title in titles:
             if isinstance(title, str) and title.strip():
                 clean.append(title.strip())

    return clean[:10]


def pick_best_title(titles: list[str]) -> str:
    if not titles:
        return ""

    # Score titles based on SEO factors but add a random element
    scored = []
    for t in titles:
        score = 0
        if "?" in t: score += 2
        for token in ["how", "what", "why", "tips", "foods", "routine", "guide", "checklist"]:
            if token in t.lower():
                score += 1
        # Add a bit of randomness to avoid picking the same style every time
        score += random.uniform(0, 1.5)
        scored.append((score, t))

    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1]
