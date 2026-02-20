from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import load_settings
from .site import write_site_state


def delete_post(slug: str, delete_hero: bool = False) -> None:
    settings = load_settings()
    docs_dir = settings.repo_root / "docs"
    post_path = docs_dir / f"{slug}.html"
    posts_path = docs_dir / "posts.json"

    posts: list[dict] = []
    if posts_path.exists():
        posts = json.loads(posts_path.read_text(encoding="utf-8"))

    removed = None
    kept: list[dict] = []
    for post in posts:
        if post.get("slug") == slug and removed is None:
            removed = post
        else:
            kept.append(post)

    if post_path.exists():
        post_path.unlink()

    if delete_hero and removed and removed.get("hero"):
        hero_path = docs_dir / str(removed["hero"])
        if hero_path.exists() and hero_path.is_file():
            hero_path.unlink()

    write_site_state(docs_dir, settings.base_url, settings.site_title, kept)


def main() -> None:
    parser = argparse.ArgumentParser(description="Delete a post and rebuild site indexes")
    parser.add_argument("--slug", required=True)
    parser.add_argument("--delete-hero", action="store_true")
    args = parser.parse_args()
    delete_post(args.slug, delete_hero=args.delete_hero)


if __name__ == "__main__":
    main()
