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


def create_pinterest_image(
    api_key: str,
    query: str,
    title: str,
    out_path: Path,
    source_image_path: Path | None = None,
) -> None:
    _ = title  # retained for backward compatibility in call sites.
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if source_image_path and source_image_path.exists():
        shutil.copyfile(source_image_path, out_path)
        return

    # Fallback to direct Pexels download when no source image path is provided.
    url = _pexels_photo_url(api_key, query)
    out_path.write_bytes(requests.get(url, timeout=40).content)
