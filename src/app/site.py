# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import date
from html import escape
from pathlib import Path

PUBLIC_BASE_URL = "https://rodrigosimoes97.github.io/Pin"


def publish_post(
    docs_dir: Path,
    base_url: str,
    site_title: str,
    post: dict[str, str],
    hero_path_rel: str,
    run_date: date,
) -> dict[str, str]:
    docs_dir.mkdir(parents=True, exist_ok=True)
    posts = _load_posts(docs_dir / "posts.json")

    tag = post.get("tag", "health")
    related = _pick_related(posts, tag, post.get("slug", ""))
    article_html, toc_items = _inject_h2_ids_and_collect_toc(post["html"])
    article_html = _inject_internal_links(article_html, related, tag)
    article_html = _append_related_posts_cards(article_html, related)

    page_html = _render_post_html(
        base_url=base_url,
        site_title=site_title,
        post=post,
        hero_path_rel=hero_path_rel,
        article_html=article_html,
        toc_items=toc_items,
        run_date=run_date,
    )
    (docs_dir / f"{post['slug']}.html").write_text(page_html, encoding="utf-8")

    record = {
        "slug": post["slug"],
        "title": post["title"],
        "description": post["meta_description"],
        "date": run_date.isoformat(),
        "url": f"{post['slug']}.html",
        "hero": hero_path_rel,
        "tag": tag,
    }
    posts = [record] + [existing for existing in posts if existing.get("slug") != post["slug"]]
    write_site_state(docs_dir, base_url, site_title, posts)
    return record


def write_site_state(docs_dir: Path, base_url: str, site_title: str, posts: list[dict[str, str]]) -> None:
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "posts.json").write_text(json.dumps(posts[:200], indent=2), encoding="utf-8")
    _write_index(docs_dir, base_url, site_title, posts)
    tag_pages = _write_tag_pages(docs_dir, base_url, site_title, posts)
    _write_sitemap(docs_dir, base_url, posts, tag_pages)
    _write_robots(docs_dir, base_url)


def _effective_base_url(base_url: str) -> str:
    return PUBLIC_BASE_URL.rstrip("/") if "rodrigosimoes97.github.io/Pin" in PUBLIC_BASE_URL else base_url.rstrip("/")


def _load_posts(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return payload if isinstance(payload, list) else []


def _inject_h2_ids_and_collect_toc(html: str) -> tuple[str, list[tuple[str, str]]]:
    pattern = re.compile(r"<h2([^>]*)>(.*?)</h2>", flags=re.IGNORECASE | re.DOTALL)
    toc_items: list[tuple[str, str]] = []

    def replace(match: re.Match[str]) -> str:
        attrs = match.group(1) or ""
        inner = match.group(2) or ""
        text = re.sub(r"<[^>]+>", "", inner).strip()
        id_match = re.search(r'id\s*=\s*["\']([^"\']+)["\']', attrs, flags=re.IGNORECASE)
        h2_id = _slugify(id_match.group(1) if id_match else text)
        toc_items.append((text, h2_id))
        if id_match:
            return f"<h2{attrs}>{inner}</h2>"
        return f"<h2{attrs} id=\"{h2_id}\">{inner}</h2>"

    return pattern.sub(replace, html), toc_items[:6]


def _inject_internal_links(html: str, related: list[dict[str, str]], tag: str) -> str:
    targets = {
        "#recent-1": related[0]["url"] if len(related) > 0 else "index.html",
        "#recent-2": related[1]["url"] if len(related) > 1 else "index.html",
        "#recent-3": related[2]["url"] if len(related) > 2 else "index.html",
        "#recent-4": related[0]["url"] if len(related) > 0 else "index.html",
        "#recent-5": f"tag/{tag}.html",
    }
    for placeholder, target in targets.items():
        html = html.replace(f'href="{placeholder}"', f'href="{target}"')
        html = html.replace(f"href='{placeholder}'", f"href='{target}'")
    return html


def _pick_related(posts: list[dict[str, str]], tag: str, current_slug: str) -> list[dict[str, str]]:
    same_tag = [post for post in posts if post.get("slug") != current_slug and post.get("tag") == tag]
    if len(same_tag) >= 3:
        return same_tag[:3]
    fallback = [post for post in posts if post.get("slug") != current_slug and post not in same_tag]
    return (same_tag + fallback)[:3]


def _append_related_posts_cards(html: str, related: list[dict[str, str]]) -> str:
    if not related:
        return html
    cards = []
    for item in related:
        image_html = ""
        if item.get("hero"):
            image_html = f"<img src='{escape(item['hero'])}' alt='{escape(item['title'])}' loading='lazy'>"
        cards.append(
            "<article class='related-card'>"
            f"{image_html}<h3><a href='{escape(item['url'])}'>{escape(item['title'])}</a></h3>"
            f"<p><a class='tag-pill' href='tag/{escape(item.get('tag', 'health'))}.html'>{escape(item.get('tag', 'health'))}</a></p>"
            "</article>"
        )
    return f"{html}\n<section class='related'><h2>Related posts</h2><div class='related-grid'>{''.join(cards)}</div></section>"


def _build_quick_answer(article_html: str) -> str:
    first_para = re.search(r"<p[^>]*>(.*?)</p>", article_html, flags=re.IGNORECASE | re.DOTALL)
    if not first_para:
        return "Practical steps and key takeaways are summarized below."
    text = re.sub(r"<[^>]+>", "", first_para.group(1)).strip()
    if not text:
        return "Practical steps and key takeaways are summarized below."
    parts = re.split(r"(?<=[.!?])\s+", text)
    return " ".join(parts[:2])[:260]


def _extract_faq_items(article_html: str) -> list[dict[str, str]]:
    faq_section = re.search(r"<h2[^>]*>\s*FAQ\s*</h2>(.*?)(?:<h2|$)", article_html, flags=re.IGNORECASE | re.DOTALL)
    if not faq_section:
        return []
    block = faq_section.group(1)
    questions = list(re.finditer(r"<h3[^>]*>(.*?)</h3>", block, flags=re.IGNORECASE | re.DOTALL))
    items: list[dict[str, str]] = []
    for idx, match in enumerate(questions):
        q = re.sub(r"<[^>]+>", "", match.group(1)).strip()
        start = match.end()
        end = questions[idx + 1].start() if idx + 1 < len(questions) else len(block)
        answer_block = block[start:end]
        p_match = re.search(r"<p[^>]*>(.*?)</p>", answer_block, flags=re.IGNORECASE | re.DOTALL)
        a = re.sub(r"<[^>]+>", "", p_match.group(1)).strip() if p_match else re.sub(r"<[^>]+>", "", answer_block).strip()
        if q and a:
            items.append({"question": q, "answer": a})
    return items[:8]


def _render_post_html(
    base_url: str,
    site_title: str,
    post: dict[str, str],
    hero_path_rel: str,
    article_html: str,
    toc_items: list[tuple[str, str]],
    run_date: date,
) -> str:
    public_base = _effective_base_url(base_url)
    canonical = f"{public_base}/{post['slug']}.html"
    tag = post.get("tag", "health")
    tag_url = f"{public_base}/tag/{tag}.html"
    og_image = f"{public_base}/{hero_path_rel}"
    description = post["meta_description"]

    toc_block = ""
    if len(toc_items) >= 2:
        toc_links = "".join(
            f"<li><a href='#{escape(h2_id)}'>{escape(title)}</a></li>" for title, h2_id in toc_items[:6]
        )
        toc_block = f"<nav class='toc'><h2>Table of contents</h2><ol>{toc_links}</ol></nav>"

    quick_answer = _build_quick_answer(article_html)

    article_schema = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": post["title"],
        "description": description,
        "datePublished": run_date.isoformat(),
        "dateModified": run_date.isoformat(),
        "author": {"@type": "Organization", "name": site_title},
        "mainEntityOfPage": canonical,
        "image": og_image,
        "about": tag,
    }

    faq_items = _extract_faq_items(article_html)
    faq_schema = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": item["question"],
                "acceptedAnswer": {"@type": "Answer", "text": item["answer"]},
            }
            for item in faq_items
        ],
    }

    breadcrumb_schema = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": f"{public_base}/index.html"},
            {"@type": "ListItem", "position": 2, "name": tag, "item": tag_url},
            {"@type": "ListItem", "position": 3, "name": post["title"], "item": canonical},
        ],
    }

    faq_jsonld = f"<script type='application/ld+json'>{json.dumps(faq_schema)}</script>" if faq_items else ""

    return f"""<!doctype html>
<html lang='en'>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width, initial-scale=1'>
<title>{escape(post['title'])}</title>
<meta name='description' content='{escape(description)}'>
<meta name='robots' content='index,follow'>
<link rel='canonical' href='{canonical}'>
<meta property='og:type' content='article'>
<meta property='og:title' content='{escape(post['title'])}'>
<meta property='og:description' content='{escape(description)}'>
<meta property='og:url' content='{canonical}'>
<meta property='og:image' content='{og_image}'>
<meta name='twitter:card' content='summary_large_image'>
<meta name='twitter:title' content='{escape(post['title'])}'>
<meta name='twitter:description' content='{escape(description)}'>
<meta name='twitter:image' content='{og_image}'>
<style>{_base_css()}</style>
<script type='application/ld+json'>{json.dumps(article_schema)}</script>
{faq_jsonld}
<script type='application/ld+json'>{json.dumps(breadcrumb_schema)}</script>
</head>
<body>
<main class='container'>
<header class='header'><a href='index.html'>{escape(site_title)}</a></header>
<article>
<h1>{escape(post['title'])}</h1>
<div class='quick-answer'><strong>Quick answer:</strong> {escape(quick_answer)}</div>
<p class='meta'>{run_date.isoformat()} · <a class='tag-pill' href='tag/{escape(tag)}.html'>{escape(tag)}</a></p>
<img src='{escape(hero_path_rel)}' alt='{escape(post['alt_text'])}' fetchpriority='high' loading='eager'>
{toc_block}
{article_html}
</article>
</main>
</body>
</html>"""


def _tag_intro(tag: str) -> str:
    readable = tag.replace("-", " ")
    return f"Explore practical {readable} guides, checklists, and step-by-step posts for daily use."


def _write_index(docs_dir: Path, base_url: str, site_title: str, posts: list[dict[str, str]]) -> None:
    public_base = _effective_base_url(base_url)
    top_tags = [tag for tag, _ in Counter((p.get("tag") or "health") for p in posts).most_common(10)]
    chips = "".join(f"<a class='tag-pill' href='tag/{escape(tag)}.html'>{escape(tag)}</a>" for tag in top_tags)
    items = "".join(
        f"<li><a href='{escape(post['url'])}'>{escape(post['title'])}</a> "
        f"<small>{escape(post['date'])}</small> "
        f"<a class='tag-pill' href='tag/{escape(post.get('tag', 'health'))}.html'>{escape(post.get('tag', 'health'))}</a></li>"
        for post in posts[:50]
    )
    html = f"""<!doctype html>
<html lang='en'>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width, initial-scale=1'>
<title>{escape(site_title)}</title>
<meta name='description' content='Practical US health content for sleep, gut health, workouts, and habits.'>
<meta name='robots' content='index,follow'>
<link rel='canonical' href='{public_base}/index.html'>
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


def _write_tag_pages(docs_dir: Path, base_url: str, site_title: str, posts: list[dict[str, str]]) -> list[str]:
    public_base = _effective_base_url(base_url)
    tag_dir = docs_dir / "tag"
    tag_dir.mkdir(parents=True, exist_ok=True)
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for post in posts:
        grouped[post.get("tag", "health")].append(post)

    urls: list[str] = []
    for tag, group in grouped.items():
        file_name = f"{tag}.html"
        urls.append(f"tag/{file_name}")
        unique_posts = group[:]
        latest = unique_posts[:8]
        popular = unique_posts[:8]
        start_here = unique_posts[:8]

        def list_html(entries: list[dict[str, str]]) -> str:
            return "".join(
                f"<li><a href='../{escape(item['url'])}'>{escape(item['title'])}</a> <small>{escape(item['date'])}</small></li>"
                for item in entries
            )

        links_count = len({p["url"] for p in unique_posts[:8]})
        note = "" if links_count >= 8 else "<p>More posts will appear here as new content is published.</p>"

        page = f"""<!doctype html>
<html lang='en'>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width, initial-scale=1'>
<title>{escape(tag)} posts | {escape(site_title)}</title>
<meta name='description' content='Newest {escape(tag)} posts'>
<meta name='robots' content='index,follow'>
<link rel='canonical' href='{public_base}/tag/{escape(file_name)}'>
<style>{_base_css()}</style>
</head>
<body>
<main class='container'>
<p><a href='../index.html'>Back to home</a></p>
<h1>{escape(tag)} hub</h1>
<p>{escape(_tag_intro(tag))}</p>
<h2>Latest</h2>
<ul>{list_html(latest)}</ul>
<h2>Popular</h2>
<ul>{list_html(popular)}</ul>
<h2>Start here</h2>
<ul>{list_html(start_here)}</ul>
{note}
</main>
</body>
</html>"""
        (tag_dir / file_name).write_text(page, encoding="utf-8")

    return urls


def _write_sitemap(docs_dir: Path, base_url: str, posts: list[dict[str, str]], tag_pages: list[str]) -> None:
    public_base = _effective_base_url(base_url)
    rows = [
        "  <url>",
        f"    <loc>{public_base}/index.html</loc>",
        f"    <lastmod>{date.today().isoformat()}</lastmod>",
        "  </url>",
    ]
    for post in posts[:200]:
        rows.extend(
            [
                "  <url>",
                f"    <loc>{public_base}/{escape(post['url'])}</loc>",
                f"    <lastmod>{escape(post.get('date', date.today().isoformat()))}</lastmod>",
                "  </url>",
            ]
        )
    for tag_page in sorted(set(tag_pages)):
        rows.extend(
            [
                "  <url>",
                f"    <loc>{public_base}/{escape(tag_page)}</loc>",
                f"    <lastmod>{date.today().isoformat()}</lastmod>",
                "  </url>",
            ]
        )
    xml = "\n".join(
        [
            "<?xml version='1.0' encoding='UTF-8'?>",
            "<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>",
            *rows,
            "</urlset>",
        ]
    )
    (docs_dir / "sitemap.xml").write_text(xml, encoding="utf-8")


def _write_robots(docs_dir: Path, base_url: str) -> None:
    public_base = _effective_base_url(base_url)
    (docs_dir / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {public_base}/sitemap.xml\n",
        encoding="utf-8",
    )


def _slugify(value: str) -> str:
    raw = re.sub(r"<[^>]+>", "", value).strip().lower()
    raw = re.sub(r"[^a-z0-9]+", "-", raw)
    raw = re.sub(r"-+", "-", raw)
    return raw.strip("-") or "section"


def _base_css() -> str:
    return (
        "body{margin:0;background:#f8fafc;color:#0f172a;font-family:Arial,sans-serif;line-height:1.65;}"
        ".container{max-width:760px;margin:0 auto;padding:16px;}"
        ".header{margin-bottom:8px;}"
        "h1{font-size:1.75rem;line-height:1.2;margin:10px 0 12px;}"
        "h2{margin-top:22px;font-size:1.35rem;}"
        "h3{margin:10px 0 6px;font-size:1.05rem;}"
        "p,li{font-size:1rem;}"
        "img{max-width:100%;height:auto;border-radius:12px;}"
        "a{color:#0f766e;text-decoration:none;}a:hover{text-decoration:underline;}"
        ".meta{color:#475569;font-size:.92rem;margin-bottom:12px;}"
        ".quick-answer{background:#ecfeff;border:1px solid #bae6fd;padding:10px 12px;border-radius:10px;margin:10px 0 12px;}"
        ".tag-row{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0 16px;}"
        ".tag-pill{display:inline-block;background:#e2e8f0;color:#0f172a;border-radius:999px;padding:2px 10px;font-size:.82rem;}"
        ".toc,.related{background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:12px;margin:16px 0;}"
        ".related-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px;}"
        ".related-card{border:1px solid #e2e8f0;border-radius:10px;padding:8px;background:#fff;}"
        ".related-card img{margin-bottom:6px;}"
        "ul,ol{padding-left:22px;}"
    )
