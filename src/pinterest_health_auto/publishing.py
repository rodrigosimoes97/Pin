from __future__ import annotations

import csv
import random
import time
from dataclasses import dataclass
from pathlib import Path

import requests

from .config import settings


@dataclass(slots=True)
class PublishPayload:
    title: str
    description: str
    board_name: str
    link: str
    image_path: str
    alt_text: str
    tags: list[str]


class PinterestPublisher:
    api_base = "https://api.pinterest.com/v5"

    def __init__(self, csv_export_path: str = "pin_export_queue.csv") -> None:
        self.csv_export_path = Path(csv_export_path)

    def publish_or_export(self, payload: PublishPayload) -> tuple[str, str]:
        if settings.pinterest_access_token:
            result = self._publish_with_retry(payload)
            if result:
                return "published", result
        self._export_csv(payload)
        return "exported", "API unavailable. Exported pin metadata to CSV fallback."

    def _publish_with_retry(self, payload: PublishPayload) -> str | None:
        headers = {
            "Authorization": f"Bearer {settings.pinterest_access_token}",
            "Content-Type": "application/json",
        }
        body = {
            "title": payload.title,
            "description": payload.description,
            "link": payload.link,
            "alt_text": payload.alt_text,
            "board_id": payload.board_name,
            "media_source": {
                "source_type": "image_base64",
                "content_type": "image/png",
                "data": "",
            },
        }

        for attempt in range(1, 5):
            try:
                response = requests.post(
                    f"{self.api_base}/pins",
                    headers=headers,
                    json=body,
                    timeout=12,
                )
                if response.status_code in {200, 201}:
                    return response.json().get("id", "unknown-pin-id")
                if response.status_code in {429, 500, 502, 503, 504}:
                    wait = (2 ** attempt) + random.uniform(0.2, 1.1)
                    time.sleep(wait)
                    continue
                return None
            except requests.RequestException:
                wait = (2 ** attempt) + random.uniform(0.2, 1.1)
                time.sleep(wait)
        return None

    def _export_csv(self, payload: PublishPayload) -> None:
        file_exists = self.csv_export_path.exists()
        with self.csv_export_path.open("a", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=[
                    "title",
                    "description",
                    "board_name",
                    "link",
                    "image_path",
                    "alt_text",
                    "tags",
                ],
            )
            if not file_exists:
                writer.writeheader()
            writer.writerow(
                {
                    "title": payload.title,
                    "description": payload.description,
                    "board_name": payload.board_name,
                    "link": payload.link,
                    "image_path": payload.image_path,
                    "alt_text": payload.alt_text,
                    "tags": ",".join(payload.tags),
                }
            )
