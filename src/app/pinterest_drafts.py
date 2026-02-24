from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path


def write_draft_pack(
    out_dir: Path,
    run_date: date,
    pin_title: str,
    pin_description: str,
    link: str,
    image_path: str,
    alt_text: str,
) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    item = {
        "title": pin_title,
        "description": pin_description,
        "link": link,
        "image_path": image_path,
        "alt_text": alt_text,
    }

    json_path = out_dir / f"{run_date.isoformat()}_pins.json"
    payload: list[dict[str, str]] = []
    if json_path.exists():
        try:
            raw = json.loads(json_path.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                for existing in raw:
                    if isinstance(existing, dict):
                        normalized = {
                            "title": str(existing.get("title", "")).strip(),
                            "description": str(existing.get("description", "")).strip(),
                            "link": str(existing.get("link", "")).strip(),
                            "image_path": str(existing.get("image_path", "")).strip(),
                            "alt_text": str(existing.get("alt_text", "")).strip(),
                        }
                        if normalized["link"]:
                            payload.append(normalized)
        except json.JSONDecodeError:
            payload = []

    seen_links = {entry["link"] for entry in payload}
    if link not in seen_links:
        payload.append(item)

    csv_path = out_dir / f"{run_date.isoformat()}_pins.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["title", "description", "link", "image_path", "alt_text"])
        writer.writeheader()
        writer.writerows(payload)

    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return csv_path, json_path
