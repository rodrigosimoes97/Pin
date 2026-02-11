from __future__ import annotations

import random
from dataclasses import dataclass

import requests


@dataclass(slots=True)
class TrendingTopic:
    name: str
    trend_score: float
    source: str


class TopicDiscovery:
    """Discovers US health & wellness trending topics with API fallback."""

    fallback_topics = [
        "metabolism boosting foods",
        "low sugar high protein snacks",
        "natural supplements for energy",
        "gut health morning routine",
        "healthy weight loss meal prep",
        "vitamin d benefits for women",
        "anti inflammatory smoothie recipes",
        "hydration tips for fat loss",
        "collagen peptides benefits",
        "magnesium for stress relief",
    ]

    def fetch_trending_topics(self, limit: int = 10) -> list[TrendingTopic]:
        topics = self._from_public_feed(limit)
        if topics:
            return topics
        return self._fallback(limit)

    def _from_public_feed(self, limit: int) -> list[TrendingTopic]:
        """Attempts to use a public feed; returns empty list if unavailable."""
        url = "https://trends.google.com/trends/api/dailytrends"
        params = {"hl": "en-US", "geo": "US", "ns": 15}
        try:
            response = requests.get(url, params=params, timeout=8)
            response.raise_for_status()
        except requests.RequestException:
            return []

        text = response.text.strip()
        if text.startswith(")]}'"):
            text = text[4:]
        try:
            payload = response.json() if isinstance(response.json(), dict) else None
        except Exception:
            import json

            payload = json.loads(text)
        if not payload:
            return []

        days = payload.get("default", {}).get("trendingSearchesDays", [])
        if not days:
            return []
        raw_topics = []
        for day in days:
            for trend in day.get("trendingSearches", []):
                title = trend.get("title", {}).get("query", "")
                if any(k in title.lower() for k in ["health", "diet", "weight", "vitamin", "recipe", "wellness"]):
                    raw_topics.append(title)
        if not raw_topics:
            return []
        unique = list(dict.fromkeys(raw_topics))[:limit]
        return [TrendingTopic(name=t, trend_score=100 - i * 4, source="google-trends") for i, t in enumerate(unique)]

    def _fallback(self, limit: int) -> list[TrendingTopic]:
        sampled = random.sample(self.fallback_topics, k=min(limit, len(self.fallback_topics)))
        return [
            TrendingTopic(name=topic, trend_score=round(random.uniform(65, 95), 2), source="fallback-seed")
            for topic in sampled
        ]
