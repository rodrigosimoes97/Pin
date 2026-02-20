from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(frozen=True)
class Topic:
    slug: str
    name: str
    angle: str
    tag: str


TOPICS: list[Topic] = [
    Topic("healthy-recipes", "Healthy Recipes", "quick meals for busy weekdays", "recipes"),
    Topic("home-exercises", "Home Exercises", "no-equipment movement plans", "exercise"),
    Topic("healthy-habits", "Healthy Habits", "small behavior changes that stick", "habits"),
    Topic("natural-remedies", "Natural Remedies", "safe lifestyle-based comfort strategies", "remedies"),
    Topic("gut-health", "Gut Health", "fiber, fermented foods, and meal timing", "gut"),
    Topic("sleep-improvement", "Sleep Improvement", "bedtime routines and wind-down habits", "sleep"),
    Topic("weight-loss-lifestyle", "Weight Loss Lifestyle", "sustainable calorie-aware choices", "weight"),
    Topic("anti-inflammatory-foods", "Anti-Inflammatory Foods", "everyday ingredients to reduce inflammation load", "anti-inflammatory"),
    Topic("mental-wellness-basics", "Mental Wellness Basics", "stress reset and emotional resilience", "mental"),
    Topic("longevity-daily-routines", "Daily Routines for Longevity", "evidence-aligned daily rhythm", "longevity"),
]


def pick_topic(recent_topics: list[str]) -> Topic:
    fresh = [topic for topic in TOPICS if topic.slug not in recent_topics[-6:]]
    pool = fresh or TOPICS
    return random.choice(pool)
