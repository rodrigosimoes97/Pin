from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class Topic:
    id: int | None
    name: str
    source: str
    trend_score: float
    locale: str = "en-US"
    created_at: datetime | None = None


@dataclass(slots=True)
class PinDraft:
    id: int | None
    topic_id: int
    board_name: str
    title: str
    description: str
    alt_text: str
    keyword_tags: list[str]
    affiliate_link: str
    image_path: str
    publish_at: datetime | None = None
    status: str = "draft"


@dataclass(slots=True)
class PublishResult:
    pin_id: int
    external_pin_id: str | None
    status: str
    message: str


@dataclass(slots=True)
class MetricEvent:
    id: int | None
    pin_id: int
    event_type: str
    value: float
    occurred_at: datetime | None = None
