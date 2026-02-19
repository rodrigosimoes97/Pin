from __future__ import annotations

import html
import json
from datetime import date
from pathlib import Path
from typing import Dict, List


POSTS_FILE = "posts.json"


def _safe_excerpt(html_blob: str, limit: int = 220) -> str:
    text = html_blob.replace("<", " ").replace(">", " ")
    compact = " ".join(text.split())
    return compact[:limit].strip() + ("..." if len(compact) > limit else "")


def _load_posts(docs_dir: Path) -> List[Dict]:
    path = docs_dir / POSTS_FILE
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _save_posts(docs_dir: Path, posts: List[Dict]) -> None:
    (docs_dir / POSTS_FILE).write_text(json.dumps(posts, indent=2), encoding="utf-8")


def publish_post(
    docs_dir: Path,
    base_url: str,
    site_title: str,
    post: dict,
    hero_path_rel: str,
    run_date: date,
) -> dict:
    docs_dir.mkdir(parents=True, exist_ok=True)
    posts = _load_posts(docs_dir)
    slug = post["slug"]
    canonical = f"{base_url}/{slug}.html"
    recent_links = ""
    for prev in posts[:3]:
        recent_links += f'<li><a href="{html.escape(prev["url"])}">{html.escape(prev["title"])}</a></li>'

    html_page = f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width,initial-scale=1\" />
  <title>{html.escape(post['title'])}</title>
  <link rel=\"canonical\" href=\"{html.escape(canonical)}\" />
  <style>
    body {{ font-family: Arial, sans-serif; max-width: 860px; margin: 0 auto; padding: 1rem; line-height: 1.6; color: #1f2937; }}
    img {{ width: 100%; border-radius: 10px; }}
    .meta {{ color: #6b7280; margin-bottom: 1rem; }}
    .note {{ background: #f3f4f6; padding: .75rem; border-radius: 8px; }}
    a {{ color: #0f766e; }}
  </style>
</head>
<body>
  <p><a href=\"index.html\">← Back to home</a></p>
  <h1>{html.escape(post['title'])}</h1>
  <p class=\"meta\">Published {run_date.isoformat()} | {html.escape(site_title)}</p>
  <img src=\"{html.escape(hero_path_rel)}\" alt=\"{html.escape(post['alt_text'])}\" />
  {post['html']}
  <section>
    <h2>Recent plans</h2>
    <ul>{recent_links}</ul>
  </section>
</body>
</html>"""

    page_path = docs_dir / f"{slug}.html"
    page_path.write_text(html_page, encoding="utf-8")

    record = {
        "title": post["title"],
        "slug": slug,
        "url": f"{slug}.html",
        "date": run_date.isoformat(),
        "excerpt": _safe_excerpt(post["html"]),
    }
    posts = [p for p in posts if p["slug"] != slug]
    posts.insert(0, record)
    _save_posts(docs_dir, posts)

    _write_index(docs_dir, site_title, posts)
    _write_sitemap(docs_dir, base_url, posts)
    _write_robots(docs_dir, base_url)
    return record


def _write_index(docs_dir: Path, site_title: str, posts: List[Dict]) -> None:
    cards = []
    for post in posts:
        cards.append(
            f"<article><h2><a href=\"{html.escape(post['url'])}\">{html.escape(post['title'])}</a></h2>"
            f"<p><small>{post['date']}</small></p><p>{html.escape(post['excerpt'])}</p></article>"
        )
    if not cards:
        cards.append("<p>No posts yet. Daily automation will add posts automatically.</p>")

    index = f"""<!doctype html>
<html lang=\"en\"><head><meta charset=\"utf-8\" /><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\" />
<title>{html.escape(site_title)}</title>
<style>body{{font-family:Arial,sans-serif;max-width:860px;margin:0 auto;padding:1rem;line-height:1.5}}article{{border-bottom:1px solid #e5e7eb;padding:.75rem 0}}</style>
</head><body>
<h1>{html.escape(site_title)}</h1>
<p>Daily educational wellness plans for US readers. Educational only — not medical advice.</p>
{''.join(cards)}
</body></html>"""
    (docs_dir / "index.html").write_text(index, encoding="utf-8")


def _write_sitemap(docs_dir: Path, base_url: str, posts: List[Dict]) -> None:
    urls = [f"<url><loc>{base_url}/index.html</loc></url>"]
    for post in posts:
        urls.append(f"<url><loc>{base_url}/{post['url']}</loc><lastmod>{post['date']}</lastmod></url>")
    xml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
        "<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">"
        + "".join(urls)
        + "</urlset>"
    )
    (docs_dir / "sitemap.xml").write_text(xml, encoding="utf-8")


def _write_robots(docs_dir: Path, base_url: str) -> None:
    robots = f"User-agent: *\nAllow: /\nSitemap: {base_url}/sitemap.xml\n"
    (docs_dir / "robots.txt").write_text(robots, encoding="utf-8")
