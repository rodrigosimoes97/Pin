from __future__ import annotations

import logging
import random
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

LOG = logging.getLogger(__name__)


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


def fetch_hero_image(api_key: str, query: str, out_path: Path) -> Path:
    """
    Baixa a imagem hero do Pexels e salva tanto como JPEG quanto WebP.
    Retorna o Path real do arquivo JPEG salvo.
    Ambas as versões (.jpeg e .webp) são gravadas para compatibilidade e performance.
    """
    jpeg_path = out_path.with_suffix(".jpeg")
    webp_path = out_path.with_suffix(".webp")
    url = _pexels_photo_url(api_key, query, "landscape")
    jpeg_path.parent.mkdir(parents=True, exist_ok=True)

    response = requests.get(url, stream=True, timeout=40)
    img = Image.open(response.raw).convert("RGB")
    # Redimensiona para hero: largura máx 1200px
    img.thumbnail((1200, 1200), Image.Resampling.LANCZOS)
    img.save(jpeg_path, "JPEG", quality=85, optimize=True)
    img.save(webp_path, "WEBP", quality=80, method=6)
    return jpeg_path


def create_pinterest_image(
    api_key: str,
    query: str,
    title: str,
    out_path: Path,
    source_image_path: Path | None = None,
    prefer_fresh_photo: bool = False,
    branding: str = "HEALTH-PTG.PAGES.DEV",
    overlay_text: bool = False,
) -> Path:
    """
    Cria a imagem vertical para o Pinterest (1000×1500, proporção 2:3).
    Por padrão (overlay_text=False), gera uma fotografia limpa e em alta resolução
    sem textos ou tarjas por cima, otimizando o apelo visual e o algoritmo do Pinterest.
    Caso overlay_text=True, aplica uma edição editorial sutil e minimalista.
    """
    # Garante extensão .png
    png_path = out_path.with_suffix(".png")
    png_path.parent.mkdir(parents=True, exist_ok=True)

    img = None
    if prefer_fresh_photo and api_key:
        try:
            url = _pexels_photo_url(api_key, query, "portrait")
            img = Image.open(requests.get(url, stream=True, timeout=40).raw)
        except Exception as exc:
            LOG.warning(f"Could not fetch fresh Pexels portrait: {exc}. Falling back to source image.")
            img = None

    if img is None:
        if source_image_path and source_image_path.exists():
            img = Image.open(source_image_path)
        else:
            jpeg_alt = source_image_path.with_suffix(".jpeg") if source_image_path else None
            if jpeg_alt and jpeg_alt.exists():
                img = Image.open(jpeg_alt)
            elif api_key:
                try:
                    url = _pexels_photo_url(api_key, query, "portrait")
                    img = Image.open(requests.get(url, stream=True, timeout=40).raw)
                except Exception:
                    img = Image.new("RGB", (1000, 1500), color=(240, 244, 248))
            else:
                img = Image.new("RGB", (1000, 1500), color=(240, 244, 248))

    img = img.convert("RGB")

    # Recorte para proporção Pinterest 2:3 (1000×1500)
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

    # Se overlay_text estiver desativado (padrão recomendado), salva a foto 100% limpa
    if not overlay_text:
        img.save(png_path, "PNG", optimize=True)
        return png_path

    # Se overlay_text estiver ativado, aplica edição editorial suave
    _apply_editorial_overlay(img, title, branding)
    img.save(png_path, "PNG", optimize=True)
    return png_path


def _apply_editorial_overlay(img: Image.Image, title: str, branding: str) -> None:
    """
    Aplica um overlay de texto moderno e sutil estilo editorial.
    Usa um gradiente suave na base e tipografia auto-ajustável.
    """
    w, h = img.size
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw_ov = ImageDraw.Draw(overlay)

    # Gradiente escuro suave na base (de y=850 a y=1500)
    gradient_start = int(h * 0.58)
    for y in range(gradient_start, h):
        factor = (y - gradient_start) / (h - gradient_start)
        alpha = int(185 * (factor ** 1.3))
        draw_ov.line([(0, y), (w, y)], fill=(12, 18, 28, alpha))

    # Badge sutil no topo (marca)
    font_paths = [
        "arial.ttf",
        "LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    font_path = next((p for p in font_paths if Path(p).exists()), "arial.ttf")

    try:
        badge_font = ImageFont.truetype(font_path, 28)
    except Exception:
        badge_font = ImageFont.load_default()

    brand_text = branding.upper()
    tb = draw_ov.textbbox((0, 0), brand_text, font=badge_font)
    bw, bh = tb[2] - tb[0], tb[3] - tb[1]
    bx, by = 60, 60
    draw_ov.rounded_rectangle([bx, by, bx + bw + 36, by + bh + 24], radius=12, fill=(0, 0, 0, 110))
    draw_ov.text((bx + 18, by + 10), brand_text, font=badge_font, fill=(240, 245, 250, 240))

    # Título com auto-fit
    title_clean = title.strip()
    words = title_clean.split()
    if len(title_clean) > 60:
        base_size = 52
        line_height = 66
    elif len(title_clean) > 40:
        base_size = 62
        line_height = 78
    else:
        base_size = 72
        line_height = 90

    try:
        title_font = ImageFont.truetype(font_path, base_size)
    except Exception:
        title_font = ImageFont.load_default()

    max_text_width = w - 140
    lines = []
    cur = []
    for word in words:
        cur.append(word)
        if draw_ov.textlength(" ".join(cur), font=title_font) > max_text_width:
            cur.pop()
            if cur:
                lines.append(" ".join(cur))
            cur = [word]
    if cur:
        lines.append(" ".join(cur))

    lines = lines[:4]
    total_text_h = len(lines) * line_height
    start_y = h - total_text_h - 100

    for i, line in enumerate(lines):
        line_y = start_y + (i * line_height)
        draw_ov.text((72, line_y + 2), line, font=title_font, fill=(0, 0, 0, 160))
        draw_ov.text((70, line_y), line, font=title_font, fill=(255, 255, 255, 255))

    img_rgba = img.convert("RGBA")
    composed = Image.alpha_composite(img_rgba, overlay)
    img.paste(composed.convert("RGB"))



