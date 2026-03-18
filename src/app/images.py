from __future__ import annotations

import random
from pathlib import Path
import requests
from PIL import Image, ImageDraw, ImageFont

def _pexels_photo_url(api_key: str, query: str, orientation: str = "landscape") -> str:
    headers = {"Authorization": api_key}
    response = requests.get(
        "https://api.pexels.com/v1/search",
        headers=headers,
        params={"query": query, "orientation": orientation, "per_page": 5},
        timeout=40,
    )
    response.raise_for_status()
    photos = response.json().get("photos", [])
    if not photos and orientation == "portrait":
        return _pexels_photo_url(api_key, query, "landscape")
    if not photos:
        raise ValueError(f"No Pexels photos for query: {query}")
    return random.choice(photos)["src"]["large2x"]

def fetch_hero_image(api_key: str, query: str, out_path: Path) -> None:
    # Garante que a extensão seja .webp para melhor performance
    webp_path = out_path.with_suffix(".webp")
    url = _pexels_photo_url(api_key, query, "landscape")
    webp_path.parent.mkdir(parents=True, exist_ok=True)
    
    response = requests.get(url, stream=True, timeout=40)
    img = Image.open(response.raw).convert("RGB")
    # Redimensiona para um tamanho razoável de hero (1200px largura)
    img.thumbnail((1200, 1200), Image.Resampling.LANCZOS)
    img.save(webp_path, "WEBP", quality=80, method=6)

def create_pinterest_image(
    api_key: str,
    query: str,
    title: str,
    out_path: Path,
    source_image_path: Path | None = None,
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if source_image_path and source_image_path.exists():
        img = Image.open(source_image_path)
    else:
        url = _pexels_photo_url(api_key, query, "portrait")
        img = Image.open(requests.get(url, stream=True, timeout=40).raw)

    img = img.convert("RGB")
    # Redimensionar para o padrão Pinterest (1000x1500)
    target_ratio = 1000 / 1500
    w, h = img.size
    current_ratio = w / h
    
    if current_ratio > target_ratio:
        new_w = int(h * target_ratio)
        offset = (w - new_w) // 2
        img = img.crop((offset, 0, offset + new_w, h))
    else:
        new_h = int(w / target_ratio)
        offset = (h - new_h) // 2
        img = img.crop((0, offset, w, offset + new_h))
        
    img = img.resize((1000, 1500), Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(img, "RGBA")
    
    try:
        font_paths = ["arial.ttf", "LiberationSans-Regular.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"]
        font_path = next((p for p in font_paths if Path(p).exists()), "arial.ttf")
        font_bold = ImageFont.truetype(font_path, 95)
        font_small = ImageFont.truetype(font_path, 40)
    except:
        font_bold = ImageFont.load_default()
        font_small = ImageFont.load_default()

    style = random.choice(["modern", "classic", "bold"])
    site_name = "PRACTICALHABITS.NET"

    if style == "modern":
        draw.rectangle([0, 0, 1000, 450], fill=(255, 255, 255, 220))
        _draw_wrapped_text(draw, title.upper(), font_bold, (20, 20, 20, 255), 50, 80, 900)
        draw.rectangle([0, 1430, 1000, 1500], fill=(29, 78, 216, 255))
        draw.text((350, 1445), site_name, font=font_small, fill=(255, 255, 255, 255))
    elif style == "classic":
        draw.rectangle([0, 1000, 1000, 1500], fill=(0, 0, 0, 180))
        _draw_wrapped_text(draw, title, font_bold, (255, 255, 255, 255), 50, 1050, 900)
        draw.text((50, 1420), site_name, font=font_small, fill=(200, 200, 200, 255))
    else:
        draw.rectangle([50, 450, 950, 1050], fill=(29, 78, 216, 230))
        draw.rectangle([60, 460, 940, 1040], outline=(255, 255, 255, 255), width=5)
        _draw_wrapped_text(draw, title, font_bold, (255, 255, 255, 255), 100, 550, 800)
        draw.text((400, 1070), site_name, font=font_small, fill=(255, 255, 255, 255))

    img.save(out_path, "PNG", quality=85)

def _draw_wrapped_text(draw, text, font, fill, x, y, max_width):
    words = text.split()
    lines = []
    current_line = []
    for word in words:
        current_line.append(word)
        if draw.textlength(" ".join(current_line), font=font) > max_width:
            current_line.pop()
            lines.append(" ".join(current_line))
            current_line = [word]
    lines.append(" ".join(current_line))
    current_y = y
    for line in lines:
        draw.text((x, current_y), line, font=font, fill=fill)
        current_y += 110 # Altura aproximada da linha
