from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    gemini_api_keys: list[str]
    gemini_model: str
    pexels_api_key: str
    base_url: str
    site_title: str
    timezone: str
    pinterest_access_token: str
    pinterest_board_id: str
    pinterest_enable_publish: bool
    posts_per_week: int
    repo_root: Path


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def _bool_flag(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _load_gemini_keys() -> list[str]:
    keys = [os.getenv(f"GEMINI_API_KEY_{idx}", "").strip() for idx in range(1, 5)]
    keys = [key for key in keys if key]
    if not keys:
        raise ValueError("At least one GEMINI_API_KEY_1..4 environment variable is required")
    return keys


def load_settings() -> Settings:
    return Settings(
        gemini_api_keys=_load_gemini_keys(),
        gemini_model="gemini-2.5-flash-lite",
        pexels_api_key=_required("PEXELS_API_KEY"),
        base_url=_required("BASE_URL").rstrip("/"),
        site_title=os.getenv("SITE_TITLE", "Practical US Health Notes").strip(),
        timezone=os.getenv("TZ", "UTC").strip(),
        pinterest_access_token=os.getenv("PINTEREST_ACCESS_TOKEN", "").strip(),
        pinterest_board_id=os.getenv("PINTEREST_BOARD_ID", "").strip(),
        pinterest_enable_publish=_bool_flag("PINTEREST_ENABLE_PUBLISH"),
        posts_per_week=int(os.getenv("POSTS_PER_WEEK", "5").strip()),
        repo_root=Path(__file__).resolve().parents[2],
    )
