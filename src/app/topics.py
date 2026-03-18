from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Topic:
    slug: str
    name: str
    angle: str
    tag: str


TOPICS: list[Topic] = [
    Topic("healthy-recipes", "Healthy Recipes", "quick nutrient-dense meals for busy US professionals", "recipes"),
    Topic("budget-meal-prep", "Budget Meal Prep", "low-cost healthy eating for US families", "recipes"),
    Topic("high-protein-breakfast", "High Protein Breakfast", "satiating morning meals for active lifestyles", "recipes"),
    Topic("home-workouts", "Home Workouts", "no-equipment strength training for small spaces", "home-workouts"),
    Topic("walking-for-fitness", "Walking for Health", "low-impact movement routines for weight management", "home-workouts"),
    Topic("yoga-for-flexibility", "Yoga and Mobility", "daily stretching routines for sedentary workers", "home-workouts"),
    Topic("healthy-habits", "Healthy Habits", "micro-habits for long-term behavior change", "healthy-habits"),
    Topic("morning-routines", "Morning Routines", "energy-boosting habits to start the day", "healthy-habits"),
    Topic("evening-routines", "Evening Routines", "digital detox and wind-down rituals", "healthy-habits"),
    Topic("stress-reset", "Stress Support", "practical nervous system regulation techniques", "stress"),
    Topic("burnout-prevention", "Burnout Prevention", "managing workplace stress and mental fatigue", "stress"),
    Topic("mindfulness-basics", "Mindfulness Basics", "simple meditation and breathing for beginners", "stress"),
    Topic("gut-health", "Gut Health", "optimizing microbiome with diverse fiber and ferments", "gut"),
    Topic("bloating-relief", "Bloating Relief", "identifying triggers and improving digestion naturally", "gut"),
    Topic("probiotic-foods", "Probiotic Foods", "incorporating traditional fermented foods into US diets", "gut"),
    Topic("sleep-improvement", "Sleep Improvement", "optimizing the bedroom environment for deep rest", "sleep"),
    Topic("circadian-rhythm", "Circadian Rhythm", "aligning light exposure and timing for better sleep", "sleep"),
    Topic("insomnia-tips", "Natural Sleep Aids", "non-supplement ways to fall asleep faster", "sleep"),
    Topic("weight-loss-lifestyle", "Weight Loss Lifestyle", "sustainable calorie awareness without restriction", "weight"),
    Topic("metabolic-health", "Metabolic Health", "understanding blood sugar and energy balance", "weight"),
    Topic("anti-inflammatory-foods", "Anti-Inflammatory Foods", "healing the body with antioxidants and healthy fats", "anti-inflammatory"),
    Topic("joint-health", "Joint Health", "nutrition and movement for mobility and comfort", "anti-inflammatory"),
    Topic("mental-wellness-basics", "Mental Wellness Basics", "building emotional resilience and self-care systems", "mental-wellness"),
    Topic("focus-and-productivity", "Focus and Clarity", "nutrition and habits for better cognitive function", "mental-wellness"),
    Topic("longevity-daily-routines", "Daily Routines for Longevity", "science-backed habits for a longer, healthier life", "longevity"),
    Topic("functional-aging", "Functional Aging", "maintaining strength and independence as you age", "longevity"),
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
