from __future__ import annotations

from io import BytesIO
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont


def _pexels_photo_url(api_key: str, query: str) -> str:
    headers = {"Authorization": api_key}
    response = requests.get(
        "https://api.pexels.com/v1/search",
        headers=headers,
        params={"query": query, "orientation": "landscape", "per_page": 1},
        timeout=40,
    )
    response.raise_for_status()
    photos = response.json().get("photos", [])
    if not photos:
        raise ValueError(f"No Pexels photos for query: {query}")
    return photos[0]["src"]["large2x"]


def fetch_hero_image(api_key: str, query: str, out_path: Path) -> None:
    url = _pexels_photo_url(api_key, query)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    content = requests.get(url, timeout=40).content
    out_path.write_bytes(content)


def create_pinterest_image(api_key: str, query: str, title: str, out_path: Path) -> None:
    url = _pexels_photo_url(api_key, query)
    image_bytes = requests.get(url, timeout=40).content
    bg = Image.open(BytesIO(image_bytes)).convert("RGB").resize((1000, 1500))

    overlay = Image.new("RGBA", bg.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rectangle((0, 900, 1000, 1500), fill=(0, 0, 0, 150))
    bg = Image.alpha_composite(bg.convert("RGBA"), overlay)

    text_draw = ImageDraw.Draw(bg)
    font = ImageFont.load_default()
    wrapped = _wrap_text(title, 28)
    text_draw.multiline_text((70, 980), wrapped, font=font, fill=(255, 255, 255), spacing=10)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    bg.convert("RGB").save(out_path, format="PNG")


def _wrap_text(text: str, width: int) -> str:
    words = text.split()
    lines: list[str] = []
    line: list[str] = []
    for word in words:
        candidate = " ".join(line + [word])
        if len(candidate) > width and line:
            lines.append(" ".join(line))
            line = [word]
        else:
            line.append(word)
    if line:
        lines.append(" ".join(line))
    return "\n".join(lines[:7])
