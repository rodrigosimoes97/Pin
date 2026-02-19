from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

import requests

LOG = logging.getLogger(__name__)


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
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    payload = {
        "board_id": board_id,
        "title": title,
        "description": description,
        "link": link,
        "media_source": {"source_type": "image_url", "url": image_url},
        "alt_text": alt_text,
    }
    stamp = datetime.now(timezone.utc).isoformat()
    log_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        response = requests.post("https://api.pinterest.com/v5/pins", headers=headers, json=payload, timeout=45)
    except requests.RequestException as exc:
        _append(log_path, f"{stamp} PIN EXCEPTION {type(exc).__name__}: {exc}")
        return False

    if response.status_code in {200, 201}:
        _append(log_path, f"{stamp} PIN OK {response.text[:240]}")
        return True

    _append(log_path, f"{stamp} PIN FAILED {response.status_code}: {response.text[:240]}")
    LOG.warning("Pinterest publish failed (%s); continuing workflow.", response.status_code)
    return False


def _append(path: Path, line: str) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"{line}\n")
