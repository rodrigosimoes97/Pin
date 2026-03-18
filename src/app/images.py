from __future__ import annotations

import shutil
from pathlib import Path

import requests


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


from __future__ import annotations

import shutil
import random
from pathlib import Path
import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter

def _pexels_photo_url(api_key: str, query: str) -> str:
    headers = {"Authorization": api_key}
    # Para Pinterest, fotos verticais (portrait) são melhores
    response = requests.get(
        "https://api.pexels.com/v1/search",
        headers=headers,
        params={"query": query, "orientation": "portrait", "per_page": 5},
        timeout=40,
    )
    response.raise_for_status()
    photos = response.json().get("photos", [])
    if not photos:
        # Tenta landscape se não achar portrait
        response = requests.get(
            "https://api.pexels.com/v1/search",
            headers=headers,
            params={"query": query, "per_page": 1},
            timeout=40,
        )
        photos = response.json().get("photos", [])
        
    if not photos:
        raise ValueError(f"No Pexels photos for query: {query}")
        
    return random.choice(photos)["src"]["large2x"]

def fetch_hero_image(api_key: str, query: str, out_path: Path) -> None:
    url = _pexels_photo_url(api_key, query)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    content = requests.get(url, timeout=40).content
    out_path.write_bytes(content)

def create_pinterest_image(
    api_key: str,
    query: str,
    title: str,
    out_path: Path,
    source_image_path: Path | None = None,
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # 1. Obter a imagem base
    if source_image_path and source_image_path.exists():
        img = Image.open(source_image_path)
    else:
        url = _pexels_photo_url(api_key, query)
        img = Image.open(requests.get(url, stream=True, timeout=40).raw)

    # 2. Redimensionar para o padrão Pinterest (1000x1500)
    img = img.convert("RGB")
    target_ratio = 1000 / 1500
    w, h = img.size
    current_ratio = w / h
    
    if current_ratio > target_ratio:
        # Muito larga
        new_w = int(h * target_ratio)
        offset = (w - new_w) // 2
        img = img.crop((offset, 0, offset + new_w, h))
    else:
        # Muito alta
        new_h = int(w / target_ratio)
        offset = (h - new_h) // 2
        img = img.crop((0, offset, w, offset + new_h))
        
    img = img.resize((1000, 1500), Image.Resampling.LANCZOS)

    # 3. Adicionar variedade visual (3 Estilos)
    style = random.choice(["modern", "classic", "bold"])
    draw = ImageDraw.Draw(img, "RGBA")
    
    # Tenta carregar uma fonte, senão usa a padrão
    try:
        # Tenta caminhos comuns para fontes no Windows/Linux
        font_paths = ["arial.ttf", "LiberationSans-Regular.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"]
        font_path = next((p for p in font_paths if Path(p).exists() or _is_font_available(p)), "arial.ttf")
        font_main = ImageFont.truetype(font_path, 80)
        font_bold = ImageFont.truetype(font_path.replace(".ttf", "bd.ttf") if "arial" in font_path else font_path, 95)
        font_small = ImageFont.truetype(font_path, 40)
    except:
        font_main = ImageFont.load_default()
        font_bold = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # Marca d'água (Brand)
    site_name = "PRACTICALHABITS.NET" # Nome do seu site para branding
    
    if style == "modern":
        # Barra branca semi-transparente no topo
        draw.rectangle([0, 0, 1000, 450], fill=(255, 255, 255, 220))
        text_color = (20, 20, 20, 255)
        _draw_wrapped_text(draw, title.upper(), font_bold, text_color, 50, 80, 900)
        # Rodapé com marca d'água
        draw.rectangle([0, 1430, 1000, 1500], fill=(29, 78, 216, 255))
        draw.text((350, 1445), site_name, font=font_small, fill=(255, 255, 255, 255))
        
    elif style == "classic":
        # Overlay escuro no rodapé
        draw.rectangle([0, 1000, 1000, 1500], fill=(0, 0, 0, 180))
        text_color = (255, 255, 255, 255)
        _draw_wrapped_text(draw, title, font_main, text_color, 50, 1050, 900)
        draw.text((50, 1420), site_name, font=font_small, fill=(200, 200, 200, 255))
        
    else: # bold
        # Caixa centralizada com borda
        draw.rectangle([50, 450, 950, 1050], fill=(29, 78, 216, 230)) # Azul Royal
        draw.rectangle([60, 460, 940, 1040], outline=(255, 255, 255, 255), width=5)
        text_color = (255, 255, 255, 255)
        _draw_wrapped_text(draw, title, font_bold, text_color, 100, 550, 800)
        draw.text((400, 1070), site_name, font=font_small, fill=(255, 255, 255, 255))

    # Salvar
    img.save(out_path, "PNG", quality=85)

def _is_font_available(font_name):
    try:
        ImageFont.truetype(font_name, 10)
        return True
    except:
        return False

def _draw_wrapped_text(draw, text, font, fill, x, y, max_width):
    words = text.split()
    lines = []
    current_line = []
    
    for word in words:
        current_line.append(word)
        # Calcula largura da linha atual
        line_text = " ".join(current_line)
        w = draw.textlength(line_text, font=font)
        if w > max_width:
            current_line.pop()
            lines.append(" ".join(current_line))
            current_line = [word]
    lines.append(" ".join(current_line))
    
    current_y = y
    for line in lines:
        draw.text((x, current_y), line, font=font, fill=fill)
        current_y += font.getbbox(line)[3] + 20
