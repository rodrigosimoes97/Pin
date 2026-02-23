from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Topic:
    slug: str
    name: str
    angle: str
    tag: str


TOPICS: list[Topic] = [
    Topic("healthy-recipes", "Healthy Recipes", "quick meals for busy weekdays", "recipes"),
    Topic("home-workouts", "Home Workouts", "no-equipment movement plans", "home-workouts"),
    Topic("healthy-habits", "Healthy Habits", "small behavior changes that stick", "healthy-habits"),
    Topic("stress-reset", "Stress Support", "daily routines to lower stress load", "stress"),
    Topic("gut-health", "Gut Health", "fiber, fermented foods, and meal timing", "gut"),
    Topic("sleep-improvement", "Sleep Improvement", "bedtime routines and wind-down habits", "sleep"),
    Topic("weight-loss-lifestyle", "Weight Loss Lifestyle", "sustainable calorie-aware choices", "weight"),
    Topic("anti-inflammatory-foods", "Anti-Inflammatory Foods", "everyday ingredients to reduce inflammation load", "anti-inflammatory"),
    Topic("mental-wellness-basics", "Mental Wellness Basics", "stress reset and emotional resilience", "mental-wellness"),
    Topic("longevity-daily-routines", "Daily Routines for Longevity", "evidence-aligned daily rhythm", "longevity"),
]

PRIORITY_TAGS = ["sleep", "gut", "stress", "healthy-habits", "longevity", "recipes"]


def pick_topic(
    recent_topics: list[str],
    recent_tags: list[str] | None = None,
    tag_counts: dict[str, int] | None = None,
    excluded_slugs: set[str] | None = None,
    topic_rotation: dict[str, int] | None = None,
) -> Topic:
    recent_tags = recent_tags or []
    tag_counts = tag_counts or {}
    excluded_slugs = excluded_slugs or set()
    topic_rotation = topic_rotation or {}

    by_tag: dict[str, list[Topic]] = {}
    for topic in TOPICS:
        by_tag.setdefault(topic.tag, []).append(topic)

    eligible_tags = [tag for tag in PRIORITY_TAGS if tag in by_tag]
    remaining = sorted(tag for tag in by_tag if tag not in PRIORITY_TAGS)
    ordered_tags = eligible_tags + remaining

    if len(recent_tags) >= 2 and recent_tags[-1] == recent_tags[-2]:
        ordered_tags = [tag for tag in ordered_tags if tag != recent_tags[-1]] or ordered_tags

    min_count = min((tag_counts.get(tag, 0) for tag in ordered_tags), default=0)
    underrepresented = [tag for tag in ordered_tags if tag_counts.get(tag, 0) == min_count]
    candidate_tags = underrepresented or ordered_tags
    chosen_tag = candidate_tags[0]

    recent_window = set(recent_topics[-12:])
    topics_for_tag = sorted(by_tag[chosen_tag], key=lambda item: item.slug)
    fresh_topics = [item for item in topics_for_tag if item.slug not in recent_window and item.slug not in excluded_slugs]
    available = fresh_topics or [item for item in topics_for_tag if item.slug not in excluded_slugs] or topics_for_tag

    rotation_index = int(topic_rotation.get(chosen_tag, 0)) % len(available)
    return available[rotation_index]
