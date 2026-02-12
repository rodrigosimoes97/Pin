from __future__ import annotations

from pathlib import Path
from urllib.parse import quote_plus
from urllib.request import urlopen

from .config import settings


class ImageGenerator:
    """Baixa uma imagem vertical da internet para usar como criativo do pin."""

    def __init__(self) -> None:
        settings.image_output_dir.mkdir(parents=True, exist_ok=True)

    def generate_pin_image(self, topic: str, template_name: str = "default") -> str:
        """Download simples de imagem (1000x1500) com fallback local."""
        safe = "_".join(topic.lower().split())[:40] or "pin"
        out = settings.image_output_dir / f"{safe}_{template_name}.jpg"

        query = quote_plus(f"{topic} health wellness")
        candidates = [
            f"https://source.unsplash.com/1000x1500/?{query}",
            f"https://picsum.photos/seed/{query}/1000/1500",
        ]

        for url in candidates:
            try:
                with urlopen(url, timeout=15) as response:
                    out.write_bytes(response.read())
                return str(out)
            except Exception:
                continue

        out.write_bytes(b"fallback-image-unavailable")
        return str(out)
