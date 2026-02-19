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
    payload = [
        {
            "title": pin_title,
            "description": pin_description,
            "link": link,
            "image_path": image_path,
            "alt_text": alt_text,
        }
    ]

    csv_path = out_dir / f"{run_date.isoformat()}_pins.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["title", "description", "link", "image_path", "alt_text"],
        )
        writer.writeheader()
        writer.writerows(payload)

    json_path = out_dir / f"{run_date.isoformat()}_pins.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return csv_path, json_path
