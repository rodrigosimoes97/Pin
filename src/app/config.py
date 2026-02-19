from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    openai_api_key: str
    pexels_api_key: str
    base_url: str
    openai_model: str
    provider: str
    pinterest_access_token: str
    pinterest_board_id: str
    pinterest_enable_publish: bool
    site_title: str
    timezone: str
    repo_root: Path


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def _bool_flag(name: str, default: str = "0") -> bool:
    raw = os.getenv(name, default).strip().lower()
    return raw in {"1", "true", "yes", "on"}


def load_settings() -> Settings:
    return Settings(
        openai_api_key=_required("OPENAI_API_KEY"),
        pexels_api_key=_required("PEXELS_API_KEY"),
        base_url=_required("BASE_URL").rstrip("/"),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip(),
        provider="openai",
        pinterest_access_token=os.getenv("PINTEREST_ACCESS_TOKEN", "").strip(),
        pinterest_board_id=os.getenv("PINTEREST_BOARD_ID", "").strip(),
        pinterest_enable_publish=_bool_flag("PINTEREST_ENABLE_PUBLISH", "0"),
        site_title=os.getenv("SITE_TITLE", "US Wellness 14-Day Plans").strip(),
        timezone=os.getenv("TZ", "UTC").strip(),
        repo_root=Path(__file__).resolve().parents[2],
    )
