from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path


from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

# O Pinterest precisa da URL pública da imagem para o Bulk Upload
PUBLIC_BASE_URL = "https://rodrigosimoes97.github.io/Pin"

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
    
    # Formato oficial do Pinterest para Bulk Upload (CSV)
    # Media URL precisa ser pública para o Pinterest baixar a imagem
    from pathlib import Path

    normalized_path = Path(image_path).as_posix()
    media_url = f"{PUBLIC_BASE_URL}/{normalized_path.lstrip('/')}"
    
    item = {
        "Board": "Health Tips & Daily Habits", # Você pode mudar o nome da pasta (Board) aqui
        "Title": pin_title,
        "Description": pin_description,
        "Link": link,
        "Media URL": media_url,
        "Alt Text": alt_text,
        "Publish Date": run_date.isoformat(),
    }

    json_path = out_dir / f"{run_date.isoformat()}_pins.json"
    payload: list[dict[str, str]] = []
    if json_path.exists():
        try:
            raw = json.loads(json_path.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                payload = [dict(entry) for entry in raw if isinstance(entry, dict)]
        except json.JSONDecodeError:
            payload = []

    # Evita duplicados no JSON do mesmo dia
    if not any(p.get("Link") == link for p in payload):
        payload.append(item)

    # Gera o CSV no formato que o Pinterest entende (Bulk Upload)
    csv_path = out_dir / f"{run_date.isoformat()}_pins.csv"
    fieldnames = ["Board", "Title", "Description", "Link", "Media URL", "Alt Text", "Publish Date"]
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(payload)

    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return csv_path, json_path
