from __future__ import annotations

import io
import textwrap
from pathlib import Path
from typing import Optional

import requests
from PIL import Image, ImageDraw, ImageFont


def _pexels_search(api_key: str, query: str, orientation: str, per_page: int = 1) -> Optional[str]:
    url = "https://api.pexels.com/v1/search"
    params = {"query": query, "orientation": orientation, "per_page": per_page}
    response = requests.get(url, headers={"Authorization": api_key}, params=params, timeout=30)
    if response.status_code >= 400:
        return None
    photos = response.json().get("photos", [])
    if not photos:
        return None
    src = photos[0].get("src", {})
    return src.get("large2x") or src.get("large") or src.get("original")


def _download_image(url: str) -> Optional[Image.Image]:
    try:
        response = requests.get(url, timeout=45)
        response.raise_for_status()
        return Image.open(io.BytesIO(response.content)).convert("RGB")
    except Exception:
        return None


def fetch_hero_image(pexels_api_key: str, query: str, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    for _ in range(3):
        image_url = _pexels_search(pexels_api_key, query, orientation="landscape")
        if image_url:
            img = _download_image(image_url)
            if img:
                img.save(out_path, format="JPEG", quality=90)
                return out_path
    fallback = Image.new("RGB", (1600, 900), color=(233, 242, 235))
    fallback.save(out_path, format="JPEG", quality=90)
    return out_path


def create_pinterest_image(
    pexels_api_key: str,
    query: str,
    pin_title: str,
    out_path: Path,
) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas = Image.new("RGB", (1000, 1500), color=(236, 246, 238))

    bg = None
    for _ in range(3):
        image_url = _pexels_search(pexels_api_key, query, orientation="portrait")
        if image_url:
            bg = _download_image(image_url)
            if bg:
                break

    if bg:
        bg = bg.resize((1000, 1500))
        canvas.paste(bg)

    overlay = Image.new("RGBA", (1000, 1500), (0, 0, 0, 92))
    canvas = Image.alpha_composite(canvas.convert("RGBA"), overlay)

    draw = ImageDraw.Draw(canvas)
    try:
        title_font = ImageFont.truetype("DejaVuSans-Bold.ttf", 68)
        footer_font = ImageFont.truetype("DejaVuSans.ttf", 34)
    except OSError:
        title_font = ImageFont.load_default()
        footer_font = ImageFont.load_default()

    wrapped = textwrap.fill(pin_title, width=18)
    bbox = draw.multiline_textbbox((0, 0), wrapped, font=title_font, align="center", spacing=14)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    tx = (1000 - tw) // 2
    ty = (1500 - th) // 2 - 90

    draw.rounded_rectangle((90, ty - 55, 910, ty + th + 55), radius=32, fill=(0, 0, 0, 125))
    draw.multiline_text((tx, ty), wrapped, fill=(255, 255, 255), font=title_font, align="center", spacing=14)

    footer = "Read the 14-day plan"
    fb = draw.textbbox((0, 0), footer, font=footer_font)
    fw = fb[2] - fb[0]
    fx = (1000 - fw) // 2
    draw.text((fx, 1408), footer, fill=(245, 245, 245), font=footer_font)

    canvas.convert("RGB").save(out_path, format="PNG")
    return out_path
