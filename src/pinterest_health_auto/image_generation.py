from __future__ import annotations

from pathlib import Path
from textwrap import fill

from .config import settings


class ImageGenerator:
    def __init__(self) -> None:
        settings.image_output_dir.mkdir(parents=True, exist_ok=True)

    def generate_pin_image(self, title: str, template_name: str = "default") -> str:
        """Generate a Pinterest-ready 1000x1500 SVG image placeholder."""
        wrapped = fill(title.upper(), width=24).replace("\n", "&#10;")
        svg = f"""<svg xmlns='http://www.w3.org/2000/svg' width='1000' height='1500' viewBox='0 0 1000 1500'>
  <rect width='1000' height='1500' fill='#f5fcf6'/>
  <rect x='0' y='0' width='1000' height='220' fill='#287355'/>
  <rect x='80' y='260' width='840' height='960' fill='none' stroke='#287355' stroke-width='8'/>
  <text x='110' y='120' font-size='52' fill='white' font-family='Arial, sans-serif' font-weight='700'>HEALTH RESET</text>
  <text x='130' y='430' font-size='64' fill='#19231e' font-family='Arial, sans-serif' font-weight='800' style='white-space: pre'>{wrapped}</text>
  <text x='130' y='1180' font-size='34' fill='#3a604c' font-family='Arial, sans-serif' font-weight='600'>SAVE FOR LATER • WELLNESS TIPS</text>
</svg>"""
        safe = "_".join(title.lower().split())[:40]
        out = settings.image_output_dir / f"{safe or 'pin'}_{template_name}.svg"
        Path(out).write_text(svg, encoding="utf-8")
        return str(out)
