from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import requests


API_URL = "https://api.pinterest.com/v5/pins"


def create_pin(
    access_token: str,
    board_id: str,
    title: str,
    description: str,
    link: str,
    image_url: str,
    alt_text: str,
    log_path: Path,
) -> bool:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).isoformat()

    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    payload = {
        "board_id": board_id,
        "title": title,
        "description": description,
        "link": link,
        "media_source": {"source_type": "image_url", "url": image_url},
        "alt_text": alt_text,
    }

    try:
        response = requests.post(API_URL, headers=headers, json=payload, timeout=45)
        if response.status_code in {200, 201}:
            log_path.write_text(f"{stamp} PIN OK {response.text}\n", encoding="utf-8")
            return True
        if response.status_code in {401, 403}:
            with log_path.open("a", encoding="utf-8") as fh:
                fh.write(f"{stamp} PIN PERMISSION ERROR {response.status_code}: {response.text}\n")
            return False
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(f"{stamp} PIN FAILED {response.status_code}: {response.text}\n")
        return False
    except Exception as exc:
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(f"{stamp} PIN EXCEPTION {type(exc).__name__}: {exc}\n")
        return False
