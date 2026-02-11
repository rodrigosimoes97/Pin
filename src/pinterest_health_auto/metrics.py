from __future__ import annotations

from datetime import datetime

import requests

from .config import settings
from .database import Database
from .models import MetricEvent


class MetricsTracker:
    api_base = "https://api.pinterest.com/v5"

    def __init__(self, db: Database) -> None:
        self.db = db

    def log_click(self, pin_id: int, clicks: float = 1) -> int:
        return self.db.insert_metric(MetricEvent(id=None, pin_id=pin_id, event_type="click", value=clicks))

    def log_conversion(self, pin_id: int, conversions: float = 1) -> int:
        return self.db.insert_metric(
            MetricEvent(id=None, pin_id=pin_id, event_type="conversion", value=conversions)
        )

    def sync_pinterest_views(self, external_pin_id: str, local_pin_id: int) -> None:
        if not settings.pinterest_access_token:
            return
        headers = {"Authorization": f"Bearer {settings.pinterest_access_token}"}
        try:
            resp = requests.get(f"{self.api_base}/pins/{external_pin_id}", headers=headers, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            views = float(data.get("organic_metrics", {}).get("impression", 0))
            self.db.insert_metric(
                MetricEvent(
                    id=None,
                    pin_id=local_pin_id,
                    event_type="view",
                    value=views,
                    occurred_at=datetime.utcnow(),
                )
            )
        except requests.RequestException:
            return
