# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import date
from html import escape
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

    related = _pick_related(posts, post.get("tag", "health"), post.get("slug", ""))
    body_html, toc_items = _inject_h2_ids_and_collect_toc(post["html"])
    body_html = _inject_internal_links(body_html, related)
    body_html = _inject_related_reading(body_html, related)

    page = _render_post_html(
        base_url=base_url,
        site_title=site_title,
        post=post,
        hero=hero_path_rel,
        html=body_html,
        toc_items=toc_items,
        run_date=run_date,
    )
    (docs_dir / f"{post['slug']}.html").write_text(page, encoding="utf-8")

    record = {
        "slug": post["slug"],
        "title": post["title"],
        "description": post["meta_description"],
        "date": run_date.isoformat(),
        "url": f"{post['slug']}.html",
        "hero": hero_path_rel,
        "tag": post.get("tag", "health"),
    }
    posts = [record] + [p for p in posts if p.get("slug") != post["slug"]]
    write_site_state(docs_dir, base_url, site_title, posts)
    return record

    recent_links = [f"{p['slug']}.html" for p in posts[:3]]
    html = _inject_internal_links(post["html"], recent_links)

def write_site_state(docs_dir: Path, base_url: str, site_title: str, posts: list[dict[str, str]]) -> None:
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "posts.json").write_text(json.dumps(posts[:200], indent=2), encoding="utf-8")
    _write_index(docs_dir, base_url, site_title, posts)
    tag_pages = _write_tag_pages(docs_dir, base_url, site_title, posts)
    _write_sitemap(docs_dir, base_url, posts, tag_pages)
    _write_robots(docs_dir, base_url)

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
        posts = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return posts if isinstance(posts, list) else []


def _inject_h2_ids_and_collect_toc(html: str) -> tuple[str, list[tuple[str, str]]]:
    pattern = re.compile(r"<h2([^>]*)>(.*?)</h2>", flags=re.IGNORECASE | re.DOTALL)
    toc: list[tuple[str, str]] = []

    def _replace(match: re.Match[str]) -> str:
        attrs = match.group(1) or ""
        inner = match.group(2) or ""
        text = re.sub(r"<[^>]+>", "", inner).strip()
        found = re.search(r'id\s*=\s*["\']([^"\']+)["\']', attrs, flags=re.IGNORECASE)
        h2_id = _slugify(found.group(1) if found else text)
        toc.append((text, h2_id))
        if found:
            return f"<h2{attrs}>{inner}</h2>"
        return f"<h2{attrs} id=\"{h2_id}\">{inner}</h2>"

    return pattern.sub(_replace, html), toc[:6]


def _pick_related(posts: list[dict[str, str]], tag: str, current_slug: str) -> list[dict[str, str]]:
    same_tag = [p for p in posts if p.get("tag") == tag and p.get("slug") != current_slug]
    if len(same_tag) >= 3:
        return same_tag[:3]
    recent = [p for p in posts if p.get("slug") != current_slug and p not in same_tag]
    return (same_tag + recent)[:3]


def _inject_internal_links(html: str, related: list[dict[str, str]]) -> str:
    mapped = {
        "#recent-1": related[0]["url"] if len(related) > 0 else "index.html",
        "#recent-2": related[1]["url"] if len(related) > 1 else "index.html",
        "#recent-3": related[2]["url"] if len(related) > 2 else "index.html",
    }
    for placeholder, target in mapped.items():
        html = html.replace(f'href="{placeholder}"', f'href="{target}"')
        html = html.replace(f"href='{placeholder}'", f"href='{target}'")
    return html


def _inject_related_reading(html: str, related: list[dict[str, str]]) -> str:
    if not related:
        return html
    items = "".join(
        f"<li><a href='{escape(item['url'])}'>{escape(item['title'])}</a> "
        f"<a class='tag-pill' href='tag/{escape(item.get('tag', 'health'))}.html'>{escape(item.get('tag', 'health'))}</a></li>"
        for item in related
    )
    return f"{html}\n<section class='related'><h2>Related reading</h2><ul>{items}</ul></section>"


def _render_post_html(
    base_url: str,
    site_title: str,
    post: dict[str, str],
    hero: str,
    html: str,
    toc_items: list[tuple[str, str]],
    run_date: date,
) -> str:
    canonical = f"{base_url}/{post['slug']}.html"
    tag = post.get("tag", "health")
    og_image = f"{base_url}/{hero}"
    toc_html = ""
    if len(toc_items) >= 2:
        items = "".join(f"<li><a href='#{escape(h2_id)}'>{escape(title)}</a></li>" for title, h2_id in toc_items[:6])
        toc_html = f"<nav class='toc'><h2>Table of contents</h2><ol>{items}</ol></nav>"

    schema = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": post["title"],
        "description": post["meta_description"],
        "datePublished": run_date.isoformat(),
        "dateModified": run_date.isoformat(),
        "author": {"@type": "Organization", "name": site_title},
        "mainEntityOfPage": canonical,
        "image": og_image,
        "about": tag,
    }

    return f"""<!doctype html>
<html lang='en'>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width, initial-scale=1'>
<title>{escape(post['title'])}</title>
<meta name='description' content='{escape(post['meta_description'])}'>
<meta name='robots' content='index,follow'>
<link rel='canonical' href='{canonical}'>
<meta property='og:type' content='article'>
<meta property='og:title' content='{escape(post['title'])}'>
<meta property='og:description' content='{escape(post['meta_description'])}'>
<meta property='og:url' content='{canonical}'>
<meta property='og:image' content='{og_image}'>
<style>{_base_css()}</style>
<script type='application/ld+json'>{json.dumps(schema)}</script>
</head>

<body>
<main class='container'>
<header class='header'><a href='index.html'>{escape(site_title)}</a></header>
<article>
<h1>{escape(post['title'])}</h1>
<p class='meta'>{run_date.isoformat()} · <a class='tag-pill' href='tag/{escape(tag)}.html'>{escape(tag)}</a></p>
<img src='{escape(hero)}' alt='{escape(post['alt_text'])}' fetchpriority='high'>
{toc_html}
{html}
</article>
</main>
</body>
</html>"""


def _write_index(docs_dir: Path, base_url: str, site_title: str, posts: list[dict[str, str]]) -> None:
    counts = Counter((p.get("tag") or "health") for p in posts)
    top_tags = [tag for tag, _ in counts.most_common(10)]
    chips = "".join(f"<a class='tag-pill' href='tag/{escape(tag)}.html'>{escape(tag)}</a>" for tag in top_tags)
    items = "".join(
        f"<li><a href='{escape(p['url'])}'>{escape(p['title'])}</a> "
        f"<small>{escape(p['date'])}</small> "
        f"<a class='tag-pill' href='tag/{escape(p.get('tag', 'health'))}.html'>{escape(p.get('tag', 'health'))}</a></li>"
        for p in posts[:50]
    )
    html = f"""<!doctype html>
<html lang='en'>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width, initial-scale=1'>
<title>{escape(site_title)}</title>
<meta name='description' content='Practical US health content for daily routines, nutrition, sleep, and wellness.'>
<meta name='robots' content='index,follow'>
<link rel='canonical' href='{base_url}/index.html'>
<style>{_base_css()}</style>
</head>
<body>
<main class='container'>
<h1>{escape(site_title)}</h1>
<p>Informational health content for US readers.</p>
<div class='tag-row'>{chips}</div>
<ul>{items}</ul>
</main>
</body>
</html>"""
    (docs_dir / "index.html").write_text(html, encoding="utf-8")

    <div class="card">
      <ul>
        {items_html}
      </ul>
    </div>
  
</body>
</html>"""
    (docs_dir / "index.html").write_text(html, encoding="utf-8")

def _write_tag_pages(docs_dir: Path, base_url: str, site_title: str, posts: list[dict[str, str]]) -> list[str]:
    tag_dir = docs_dir / "tag"
    tag_dir.mkdir(parents=True, exist_ok=True)
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for post in posts:
        grouped[post.get("tag", "health")].append(post)

    urls: list[str] = []
    for tag, entries in grouped.items():
        file_name = f"{tag}.html"
        urls.append(f"tag/{file_name}")
        items = "".join(
            f"<li><a href='../{escape(item['url'])}'>{escape(item['title'])}</a> <small>{escape(item['date'])}</small></li>"
            for item in entries[:100]
        )
        html = f"""<!doctype html>
<html lang='en'>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width, initial-scale=1'>
<title>{escape(tag)} posts | {escape(site_title)}</title>
<meta name='description' content='Newest {escape(tag)} posts'>
<meta name='robots' content='index,follow'>
<link rel='canonical' href='{base_url}/tag/{escape(file_name)}'>
<style>{_base_css()}</style>
</head>
<body>
<main class='container'>
<p><a href='../index.html'>← Home</a></p>
<h1>{escape(tag)} posts</h1>
<ul>{items}</ul>
</main>
</body>
</html>"""
        (tag_dir / file_name).write_text(html, encoding="utf-8")
    return urls


def _write_sitemap(docs_dir: Path, base_url: str, posts: list[dict[str, str]], tag_pages: list[str]) -> None:
    rows = [f"<url><loc>{base_url}/index.html</loc></url>"]
    rows.extend(f"<url><loc>{base_url}/{escape(post['url'])}</loc></url>" for post in posts[:200])
    rows.extend(f"<url><loc>{base_url}/{escape(tag_url)}</loc></url>" for tag_url in sorted(set(tag_pages)))
    xml = (
        "<?xml version='1.0' encoding='UTF-8'?>\n"
        "<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>"
        + "".join(rows)
        + "</urlset>"
    )
    (docs_dir / "sitemap.xml").write_text(xml, encoding="utf-8")


def _write_robots(docs_dir: Path, base_url: str) -> None:
    (docs_dir / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {base_url}/sitemap.xml\n",
        encoding="utf-8",
    )


def _slugify(value: str) -> str:
    cleaned = re.sub(r"<[^>]+>", "", value).strip().lower()
    cleaned = re.sub(r"[^a-z0-9]+", "-", cleaned)
    cleaned = re.sub(r"-+", "-", cleaned)
    return cleaned.strip("-") or "section"


def _base_css() -> str:
    return (
        "body{margin:0;background:#f8fafc;color:#0f172a;font-family:Arial,sans-serif;line-height:1.65;}"
        ".container{max-width:760px;margin:0 auto;padding:16px;}"
        "h1{font-size:1.7rem;line-height:1.25;margin:8px 0 12px;}"
        "h2{margin-top:24px;} p,li{font-size:1rem;}"
        "img{max-width:100%;height:auto;border-radius:12px;}"
        "a{color:#0f766e;text-decoration:none;}a:hover{text-decoration:underline;}"
        ".meta{color:#475569;font-size:.92rem;margin-bottom:12px;}"
        ".tag-row{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0 16px;}"
        ".tag-pill{display:inline-block;background:#e2e8f0;color:#0f172a;border-radius:999px;padding:2px 10px;font-size:.82rem;}"
        ".toc,.related{background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:12px;margin:16px 0;}"
        "ul,ol{padding-left:22px;}"
    )
