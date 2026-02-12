from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(slots=True)
class PinIdea:
    title: str
    description: str
    tags: list[str]
    alt_text: str


class ContentGenerator:
    hooks = [
        "Top",
        "Simple",
        "Doctor-Loved",
        "Beginner-Friendly",
        "Science-Backed",
        "Game-Changing",
    ]
    pain_points = [
        "boost metabolism",
        "reduce cravings",
        "support gut health",
        "improve energy",
        "burn fat naturally",
        "stay full longer",
    ]

    def generate_pin_ideas(self, topic: str, count: int = 10) -> list[PinIdea]:
        count = max(5, min(20, count))
        ideas: list[PinIdea] = []
        base_tags = self._base_tags(topic)
        for idx in range(count):
            hook = random.choice(self.hooks)
            pain = random.choice(self.pain_points)
            title = f"{hook} {topic.title()} Tips to {pain.title()} in 2026"
            description = (
                f"Looking for practical ways to {pain}? This US-focused guide shares wellness-friendly "
                f"habits, supplement picks, and easy wins around {topic}. Save this pin and try one change today."
            )
            alt_text = f"Pinterest pin about {topic} with actionable tips to {pain}."
            tags = (base_tags + [pain.replace(" ", "-"), "us-wellness"])[:10]
            ideas.append(PinIdea(title=title[:100], description=description[:500], tags=tags, alt_text=alt_text))
            if idx % 3 == 0:
                random.shuffle(base_tags)
        return ideas

    def _base_tags(self, topic: str) -> list[str]:
        cleaned = topic.lower().replace(" ", "-")
        tags = [
            cleaned,
            "health-tips",
            "wellness",
            "weight-loss",
            "natural-supplements",
            "healthy-lifestyle",
            "pinterest-seo",
            "iherb-finds",
            "healthy-recipes",
            "us-health",
        ]
        return tags[:10]
