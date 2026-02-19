from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_STATE = {
    "runs": 0,
    "offer_runs": 0,
    "recent_topics": [],
    "recent_slugs": [],
    "last_run": None,
}


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return DEFAULT_STATE.copy()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return DEFAULT_STATE.copy()
    merged = DEFAULT_STATE.copy()
    merged.update(data)
    return merged


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")
