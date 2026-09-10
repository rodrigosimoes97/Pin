from __future__ import annotations

import csv
import json
from datetime import date, timezone, datetime
from pathlib import Path

# URL base pública do site
PUBLIC_BASE_URL = "https://health-ptg.pages.dev"

# Nome do board conforme o teste.csv
PINTEREST_BOARD = "Health & Wellness"

# Horário de publicação padrão (meio-dia UTC)
PUBLISH_TIME = "T12:00:00"


def write_draft_pack(
    out_dir: Path,
    run_date: date,
    pin_title: str,
    pin_description: str,
    link: str,
    image_path: str,          # caminho relativo da imagem hero (assets/YYYY-MM-DD_slug.jpeg)
    tag: str = "",            # usado para gerar Keywords
    alt_text: str = "",       # ignorado — mantido por compatibilidade retroativa
) -> tuple[Path, Path]:
    """
    Gera CSV no formato exato do Pinterest Bulk Upload (mesmo padrão do teste.csv):
    Title, Media URL, Pinterest board, Thumbnail, Description, Link, Publish date, Keywords

    A Media URL aponta para a imagem hero pública (.jpeg) — não para generated/pinterest/.
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    # Garante URL pública da imagem hero (ex: /assets/2026-09-10_slug.jpeg)
    normalized = Path(image_path).as_posix().lstrip("/")
    media_url = f"{PUBLIC_BASE_URL}/{normalized}"

    # Gera keywords a partir do tag e do título
    keywords = _build_keywords(pin_title, tag)

    # Publish date no formato ISO com hora, igual ao teste.csv
    publish_date = f"{run_date.isoformat()}{PUBLISH_TIME}"

    item = {
        "Title": pin_title,
        "Media URL": media_url,
        "Pinterest board": PINTEREST_BOARD,
        "Thumbnail": "",          # Pinterest Bulk Upload aceita vazio
        "Description": pin_description,
        "Link": link,
        "Publish date": publish_date,
        "Keywords": keywords,
    }

    # Acumula no JSON do dia para não sobrescrever pins anteriores
    json_path = out_dir / f"{run_date.isoformat()}_pins.json"
    payload: list[dict[str, str]] = []
    if json_path.exists():
        try:
            raw = json.loads(json_path.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                payload = [dict(entry) for entry in raw if isinstance(entry, dict)]
        except json.JSONDecodeError:
            payload = []

    # Evita duplicados pelo link
    if not any(p.get("Link") == link for p in payload):
        payload.append(item)

    # Fieldnames na ordem exata do teste.csv
    fieldnames = [
        "Title",
        "Media URL",
        "Pinterest board",
        "Thumbnail",
        "Description",
        "Link",
        "Publish date",
        "Keywords",
    ]

    csv_path = out_dir / f"{run_date.isoformat()}_pins.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        # Header sem aspas (padrão Pinterest Bulk Upload — igual ao teste.csv)
        handle.write(",".join(fieldnames) + "\r\n")
        # Valores com aspas usando QUOTE_NONNUMERIC
        writer = csv.DictWriter(handle, fieldnames=fieldnames, quoting=csv.QUOTE_NONNUMERIC)
        writer.writerows(payload)

    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return csv_path, json_path


def _build_keywords(title: str, tag: str) -> str:
    """Gera keywords a partir do tag e das palavras-chave do título."""
    keywords: list[str] = []

    # Tag do artigo como keyword principal
    if tag:
        keywords.append(tag.replace("-", " "))

    # Extrai substantivos/adjetivos relevantes do título (palavras longas, sem stopwords)
    STOPWORDS = {
        "a", "an", "the", "and", "or", "but", "for", "with", "this",
        "that", "your", "from", "how", "to", "of", "in", "on", "at",
        "is", "it", "my", "me", "i", "you", "we", "be", "do", "get",
        "can", "more", "less", "what", "why", "when", "which", "make",
        "feel", "start", "try", "stop", "build", "help", "keep", "give",
    }
    for word in title.lower().split():
        clean = word.strip("?!.,:")
        if len(clean) > 4 and clean not in STOPWORDS and clean not in keywords:
            keywords.append(clean)
        if len(keywords) >= 5:
            break

    # Adiciona termos de saúde sempre relevantes
    health_terms = ["healthy eating", "wellness"]
    for term in health_terms:
        if term not in keywords and len(keywords) < 6:
            keywords.append(term)

    return ",".join(keywords[:6])
