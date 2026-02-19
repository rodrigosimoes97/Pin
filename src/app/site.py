from __future__ import annotations

import json
from datetime import date
from pathlib import Path


def publish_post(
    docs_dir: Path,
    base_url: str,
    site_title: str,
    post: dict[str, str],
    hero_path_rel: str,
    run_date: date,
) -> dict[str, str]:
    docs_dir.mkdir(parents=True, exist_ok=True)
    posts_path = docs_dir / "posts.json"
    posts = _load_posts(posts_path)

    recent_links = [f"{p['slug']}.html" for p in posts[:3]]
    html = _inject_internal_links(post["html"], recent_links)

    page = _render_post_html(base_url, site_title, post, hero_path_rel, html)
    page_path = docs_dir / f"{post['slug']}.html"
    page_path.write_text(page, encoding="utf-8")

    record = {
        "slug": post["slug"],
        "title": post["title"],
        "description": post["meta_description"],
        "date": run_date.isoformat(),
        "url": f"{post['slug']}.html",
        "hero": hero_path_rel,
    }
    posts = [record] + [p for p in posts if p.get("slug") != post["slug"]]
    posts_path.write_text(json.dumps(posts[:200], indent=2), encoding="utf-8")

    _write_index(docs_dir, base_url, site_title, posts)
    _write_sitemap(docs_dir, base_url, posts)
    _write_robots(docs_dir, base_url)
    return record


def _load_posts(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


def _inject_internal_links(html: str, links: list[str]) -> str:
    mapped = {
        "#recent-1": links[0] if len(links) > 0 else "index.html",
        "#recent-2": links[1] if len(links) > 1 else "index.html",
        "#recent-3": links[2] if len(links) > 2 else "index.html",
    }
    for placeholder, target in mapped.items():
        html = html.replace(f'href="{placeholder}"', f'href="{target}"')
    return html


def _render_post_html(base_url: str, site_title: str, post: dict[str, str], hero: str, html: str) -> str:
    canonical = f"{base_url}/{post['slug']}.html"
    return f"""<!doctype html>
<html lang='en'>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width, initial-scale=1'>
<title>{post['title']}</title>
<meta name='description' content='{post['meta_description']}'>
<link rel='canonical' href='{canonical}'>
</head>
<body>
<header><a href='index.html'>{site_title}</a></header>
<article>
<h1>{post['title']}</h1>
<img src='{hero}' alt='{post['alt_text']}' loading='lazy'>
{html}
</article>
</body>
</html>"""


def _write_index(docs_dir: Path, base_url: str, site_title: str, posts: list[dict[str, str]]) -> None:
    items = "\n".join(
        f"<li><a href='{p['url']}'>{p['title']}</a> <small>{p['date']}</small></li>" for p in posts[:50]
    )
    html = f"""<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'><title>{site_title}</title><link rel='canonical' href='{base_url}/index.html'></head><body><h1>{site_title}</h1><p>Informational health content for US readers.</p><ul>{items}</ul></body></html>"""
    (docs_dir / "index.html").write_text(html, encoding="utf-8")


def _write_sitemap(docs_dir: Path, base_url: str, posts: list[dict[str, str]]) -> None:
    rows = [f"<url><loc>{base_url}/index.html</loc></url>"]
    rows.extend(f"<url><loc>{base_url}/{p['url']}</loc></url>" for p in posts[:200])
    xml = "<?xml version='1.0' encoding='UTF-8'?>\n<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>" + "".join(rows) + "</urlset>"
    (docs_dir / "sitemap.xml").write_text(xml, encoding="utf-8")


def _write_robots(docs_dir: Path, base_url: str) -> None:
    (docs_dir / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {base_url}/sitemap.xml\n", encoding="utf-8")
