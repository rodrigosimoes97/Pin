from __future__ import annotations

import csv
import json
import logging
from datetime import date
from pathlib import Path

LOG = logging.getLogger(__name__)

# URL base pública do site
PUBLIC_BASE_URL = "https://health-ptg.pages.dev"

# Nome do board conforme o teste.csv
PINTEREST_BOARD = "Health & Wellness"

# Melhores horários para postar no Pinterest (Horário dos EUA - Eastern Time / ET):
# Slot 1: 10:00 AM (Início da manhã / pausas de trabalho)
# Slot 2: 01:00 PM (13:00 - Almoço)
# Slot 3: 03:30 PM (15:30 - Pausa da tarde)
# Slot 4: 06:00 PM (18:00 - Pós-expediente / relaxamento)
# Slot 5: 08:30 PM (20:30 - Horário nobre do Pinterest / noite)
PINTEREST_BEST_HOURS_US = [
    "T10:00:00",
    "T13:00:00",
    "T15:30:00",
    "T18:00:00",
    "T20:30:00",
]


def write_draft_pack(
    out_dir: Path,
    run_date: date,
    pin_title: str,
    pin_description: str,
    link: str,
    image_path: str,          # caminho relativo da imagem hero (assets/YYYY-MM-DD_slug.jpeg)
    tag: str = "",            # usado para gerar Keywords caso não informadas
    alt_text: str = "",       # ignorado — mantido por compatibilidade retroativa
    slot_index: int | None = None,
    keywords: str = "",       # Frases de busca pré-geradas (opcional)
    intent: str = "",         # Search intent (opcional)
    primary_keyword: str = "",# Keyword principal (opcional)
) -> tuple[Path, Path]:
    """
    Gera CSV no formato exato do Pinterest Bulk Upload (mesmo padrão do teste.csv):
    Title, Media URL, Pinterest board, Thumbnail, Description, Link, Publish date, Keywords

    A Media URL aponta para a imagem hero pública (.jpeg) — não para generated/pinterest/.
    O Publish date distribui horários distintos ao longo do dia (melhores horários dos EUA).
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    # Garante URL pública da imagem hero (ex: /assets/2026-09-10_slug.jpeg)
    normalized = Path(image_path).as_posix().lstrip("/")
    media_url = f"{PUBLIC_BASE_URL}/{normalized}"

    # Usa as keywords fornecidas ou gera 5-8 long-tail search phrases
    final_keywords = (keywords or "").strip()
    if not final_keywords:
        final_keywords = _build_keywords(
            title=pin_title,
            tag=tag,
            intent=intent,
            primary_keyword=primary_keyword,
        )

    # Carrega pins já registrados no dia para determinar o slot atual caso não informado
    json_path = out_dir / f"{run_date.isoformat()}_pins.json"
    payload: list[dict[str, str]] = []
    if json_path.exists():
        try:
            raw = json.loads(json_path.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                payload = [dict(entry) for entry in raw if isinstance(entry, dict)]
        except json.JSONDecodeError:
            payload = []

    # Determina o horário do post baseado no slot (0 a 4)
    if slot_index is not None:
        idx = min(max(0, slot_index), len(PINTEREST_BEST_HOURS_US) - 1)
    else:
        idx = min(len(payload), len(PINTEREST_BEST_HOURS_US) - 1)

    publish_time = PINTEREST_BEST_HOURS_US[idx]
    publish_date = f"{run_date.isoformat()}{publish_time}"

    item = {
        "Title": pin_title,
        "Media URL": media_url,
        "Pinterest board": PINTEREST_BOARD,
        "Thumbnail": "",          # Pinterest Bulk Upload aceita vazio
        "Description": pin_description,
        "Link": link,
        "Publish date": publish_date,
        "Keywords": final_keywords,
    }

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
    LOG.info("[PinterestDrafts] Draft salvo: %s com %d keywords", csv_path.name, len(final_keywords.split(",")))
    return csv_path, json_path


def _build_keywords(
    title: str,
    tag: str,
    intent: str = "",
    primary_keyword: str = "",
) -> str:
    """
    Gera de 5 a 8 frases de busca / long-tail keywords naturais para o Pinterest.
    NÃO gera palavras isoladas soltas.
    """
    from .pinterest_seo import generate_search_keywords

    kws = generate_search_keywords(
        topic_name=title,
        title=title,
        tag=tag,
        intent=intent or "guide",
        primary_keyword=primary_keyword,
    )
    return ", ".join(kws)
