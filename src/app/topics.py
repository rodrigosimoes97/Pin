from __future__ import annotations

import json
import random
import re
from pathlib import Path
from typing import Dict, List

TOPIC_POOLS: Dict[str, List[str]] = {
    "anti-inflammatory": [
        "14-day anti-inflammatory meal prep for busy adults",
        "simple anti-inflammatory breakfast and lunch rotation",
        "budget anti-inflammatory eating for two weeks",
        "anti-inflammatory pantry reset for US families",
    ],
    "meal-prep": [
        "14-day meal prep system for healthy weekdays",
        "no-stress Sunday prep plan for two weeks",
        "high-protein lunch prep plan for adults",
        "time-saving freezer prep for balanced meals",
    ],
    "sleep": [
        "14-day better sleep routine with food timing",
        "evening habits and meals for deeper sleep",
        "caffeine cutoff and dinner plan for sleep",
        "two-week wind-down routine for busy workers",
    ],
    "gut": [
        "14-day gut-friendly meal plan with fiber goals",
        "prebiotic and probiotic food routine for beginners",
        "gentle digestion support plan for two weeks",
        "gut health grocery and prep guide for adults",
    ],
    "weight": [
        "14-day balanced weight management meal roadmap",
        "portion-friendly meal prep for sustainable fat loss",
        "high-satiety food strategy for two weeks",
        "daily walking and meal structure plan for weight goals",
    ],
}


def slugify(text: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return re.sub(r"-+", "-", cleaned)


def _state_path(repo_root: Path) -> Path:
    return repo_root / "generated" / "state.json"


def _read_state(repo_root: Path) -> dict:
    path = _state_path(repo_root)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def recent_slugs(repo_root: Path, limit: int = 30) -> List[str]:
    state = _read_state(repo_root)
    return state.get("recent_topics", [])[-limit:]


def pick_topic(repo_root: Path) -> dict:
    used = set(recent_slugs(repo_root, limit=30))
    candidates = []
    for tag, topics in TOPIC_POOLS.items():
        for topic in topics:
            slug = slugify(topic)
            if slug not in used:
                candidates.append({"tag": tag, "topic": topic, "slug": slug})

    if not candidates:
        for tag, topics in TOPIC_POOLS.items():
            for topic in topics:
                candidates.append({"tag": tag, "topic": topic, "slug": slugify(topic)})

    return random.choice(candidates)
