from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

# We reuse the site's generators to rebuild index/sitemap/tag pages after deletion.
from . import site as site_mod


def _load_posts(posts_path: Path) -> list[dict[str, Any]]:
    if not posts_path.exists():
        return []
    try:
        data = json.loads(posts_path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def main() -> None:
    ap = argparse.ArgumentParser(description="Delete a published post by slug and rebuild site files.")
    ap.add_argument("--slug", required=True, help="Slug to delete (e.g., natural-discomfort-relief-daily-habits)")
    ap.add_argument("--docs-dir", default="docs", help="Docs directory (GitHub Pages folder). Default: docs")
    ap.add_argument("--base-url", default=os.getenv("BASE_URL", "").strip(), help="Base URL, e.g. https://user.github.io/Pin")
    ap.add_argument("--site-title", default=os.getenv("SITE_TITLE", "Health Notes").strip(), help="Site title used in index")
    ap.add_argument("--delete-hero", action="store_true", help="Also delete the hero image if it exists")
    args = ap.parse_args()

    slug = args.slug.strip()
    if not slug:
        raise SystemExit("Empty slug.")

    docs_dir = Path(args.docs_dir)
    posts_path = docs_dir / "posts.json"
    posts = _load_posts(posts_path)

    # Delete HTML page if present
    page_path = docs_dir / f"{slug}.html"
    if page_path.exists():
        page_path.unlink()

    # Find record (to optionally delete hero)
    removed = [p for p in posts if p.get("slug") == slug]
    posts = [p for p in posts if p.get("slug") != slug]

    # Optionally delete hero asset referenced by record
    if args.delete_hero and removed:
        hero = (removed[0].get("hero") or "").strip()
        if hero:
            hero_path = (docs_dir / hero).resolve()
            # Safety: only delete inside docs_dir
            try:
                if str(hero_path).startswith(str(docs_dir.resolve())) and hero_path.exists():
                    hero_path.unlink()
            except Exception:
                pass

    # Persist updated posts.json
    posts_path.write_text(json.dumps(posts[:400], indent=2), encoding="utf-8")

    # Rebuild derived pages (index, tags, sitemap, robots)
    if not args.base_url:
        raise SystemExit("BASE_URL missing. Provide --base-url or set BASE_URL env var.")
    base_url = args.base_url.rstrip("/")
    site_title = args.site_title or "Health Notes"

    site_mod._write_index(docs_dir, base_url, site_title, posts)
    site_mod._write_tag_pages(docs_dir, base_url, site_title, posts)
    site_mod._write_sitemap(docs_dir, base_url, posts)
    site_mod._write_robots(docs_dir, base_url)

    print(f"Deleted slug='{slug}'. Rebuilt index/sitemap/tag pages.")


if __name__ == "__main__":
    main()
