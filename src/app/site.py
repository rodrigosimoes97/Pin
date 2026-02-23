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
    post: dict[str, object],
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
    _write_about_page(docs_dir, base_url, site_title)
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
    post: dict[str, object],
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
        "author": {"@type": "Person", "name": "RodrigoS"},
        "mainEntityOfPage": canonical,
        "image": og_image,
        "about": tag,
    }

    faq_items_raw = post.get("faq")
    faq_items = faq_items_raw if isinstance(faq_items_raw, list) else _extract_faq_items(article_html)
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
<nav class='top-nav'><a href='/Pin/'>Home</a><span>·</span><a href='/Pin/tag/{escape(tag)}.html'>{escape(tag)}</a></nav>
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
    latest_url = escape(posts[0]["url"]) if posts else "#posts"
    cards = "".join(_render_index_card(post, docs_dir) for post in posts[:50])
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
<header class='site-header'>
<div class='container header-inner'>
<div>
<a class='site-title' href='/Pin/'>{escape(site_title)}</a>
<p class='site-subtitle'>US-focused health tips, habits, and recipes</p>
</div>
<nav class='site-nav'>
<a class='active' href='index.html'>Home</a>
<a href='#tags'>Tags</a>
<a href='about.html'>About</a>
</nav>
</div>
</header>
<main class='container'>
<section class='hero'>
<h1>{escape(site_title)}</h1>
<p class='hero-intro'>Evidence-informed, practical health guides for US readers on sleep, longevity, gut health, stress, and simple recipes.</p>
<a class='btn-primary' href='{latest_url}'>Read the latest</a>
</section>

<section id='posts'>
<h2 class='section-title'>Latest posts</h2>
<div class='post-grid'>{cards}</div>
</section>

<section id='tags'>
<h2 class='section-title'>Browse by topic</h2>
<div class='tag-row'>{chips}</div>
</section>
</main>
</body>
</html>"""
    (docs_dir / "index.html").write_text(html, encoding="utf-8")


def _render_index_card(post: dict[str, str], docs_dir: Path) -> str:
    hero = (post.get("hero") or "").strip()
    title = escape(post["title"])
    tag = escape(post.get("tag", "health"))
    excerpt = escape(_post_excerpt(post, docs_dir))
    media = (
        f"<img src='{escape(hero)}' alt='{title}' loading='lazy'>"
        if hero
        else "<div class='placeholder' aria-hidden='true'></div>"
    )
    return (
        "<article class='post-card'>"
        f"<a class='card-media' href='{escape(post['url'])}'>{media}</a>"
        f"<h3><a href='{escape(post['url'])}'>{title}</a></h3>"
        f"<p class='meta'>{escape(post['date'])} · "
        f"<a class='tag-pill' href='tag/{tag}.html'>{tag}</a></p>"
        f"<p class='excerpt'>{excerpt}</p>"
        f"<a class='read-more' href='{escape(post['url'])}'>Read more →</a>"
        "</article>"
    )


def _post_excerpt(post: dict[str, str], docs_dir: Path) -> str:
    description = (post.get("description") or "").strip()
    if description:
        return description[:140].rstrip()
    url = post.get("url", "")
    target = docs_dir / url
    if target.exists():
        html = target.read_text(encoding="utf-8")
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            return text[:140].rstrip()
    return "Practical, easy-to-read tips to support your daily health habits."


def _write_about_page(docs_dir: Path, base_url: str, site_title: str) -> None:
    public_base = _effective_base_url(base_url)
    html = f"""<!doctype html>
<html lang='en'>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width, initial-scale=1'>
<title>About | {escape(site_title)}</title>
<meta name='description' content='About this health content site and editorial standards.'>
<meta name='robots' content='index,follow'>
<link rel='canonical' href='{public_base}/about.html'>
<style>{_base_css()}</style>
</head>
<body>
<main class='container'>
<header class='header'><a href='index.html'>{escape(site_title)}</a></header>
<h1>About</h1>
<p>This site publishes practical, US-focused health content designed to be clear, useful, and easy to apply in daily life.</p>
<h2>Editorial note</h2>
<p>Content is for informational purposes only and is not medical advice, diagnosis, or treatment. Always consult a qualified healthcare professional for personal medical guidance.</p>
<h2>Contact</h2>
<p>Questions or suggestions are welcome. A contact channel may be added in a future update.</p>
</main>
</body>
</html>"""
    (docs_dir / "about.html").write_text(html, encoding="utf-8")


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
        "  <url>",
        f"    <loc>{public_base}/about.html</loc>",
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
        "body{margin:0;background:#070b12;color:#e6edf6;"
        "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;"
        "line-height:1.7;}"
        ".container{max-width:1080px;margin:0 auto;padding:18px 14px 60px;}"
        ".site-header{position:sticky;top:0;z-index:20;background:rgba(7,11,18,.92);backdrop-filter:blur(8px);border-bottom:1px solid #1b2533;}"
        ".header-inner{padding-top:10px;padding-bottom:10px;display:flex;justify-content:space-between;gap:18px;align-items:center;}"
        ".site-title{font-size:18px;font-weight:700;color:#f8fbff;}"
        ".site-subtitle{margin:2px 0 0;color:#9fb0c3;font-size:13px;line-height:1.4;}"
        ".site-nav{display:flex;flex-wrap:wrap;gap:14px;font-size:14px;}"
        ".site-nav a{color:#b8d8ff;font-weight:600;}"
        ".site-nav a.active{color:#f4f8ff;}"
        ".header{margin:10px 0 14px;font-weight:700;}"
        ".header a{color:#f8fbff;}"
        ".top-nav{display:flex;align-items:center;gap:8px;margin:2px 0 10px;font-size:14px;color:#9fb0c3;}"
        ".top-nav a{color:#98d8ff;font-weight:600;}"
        ".top-nav span{opacity:.7;}"
        ".hero{padding:20px 0 10px;}"
        ".hero-intro{max-width:740px;color:#c3cfde;margin-top:0;}"
        ".btn-primary{display:inline-block;margin-top:8px;background:#1d4ed8;border:1px solid #3765e6;color:#f8fbff;padding:9px 14px;border-radius:10px;font-weight:600;transition:transform .16s ease,background .16s ease;}"
        ".btn-primary:hover{text-decoration:none;background:#2a5ce8;transform:translateY(-1px);}"
        ".section-title{margin:18px 0 12px;}"
        ".post-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px;}"
        ".post-card{background:#0b1320;border:1px solid #223247;border-radius:14px;padding:12px;box-shadow:0 10px 24px rgba(0,0,0,.22);transition:transform .16s ease,border-color .16s ease,box-shadow .16s ease;}"
        ".post-card:hover{transform:translateY(-2px);border-color:#355176;box-shadow:0 14px 28px rgba(0,0,0,.28);}"
        ".card-media{display:block;border-radius:12px;overflow:hidden;border:1px solid #1f2a3a;aspect-ratio:16/10;background:#0f1a2a;margin-bottom:10px;}"
        ".card-media img{width:100%;height:100%;object-fit:cover;margin:0;border:none;border-radius:0;}"
        ".card-media .placeholder{width:100%;height:100%;background:linear-gradient(135deg,#0e1b2f,#17263d);}"
        ".post-card h3{margin:6px 0 6px;font-size:19px;line-height:1.35;}"
        ".post-card .meta{margin:0 0 8px;}"
        ".excerpt{margin:0 0 8px;color:#c5d2e3;font-size:15px;line-height:1.55;}"
        ".read-more{font-size:14px;font-weight:600;color:#9ad8ff;}"
        "h1{font-size:clamp(26px,4.2vw,40px);line-height:1.15;margin:10px 0 12px;letter-spacing:-0.02em;}"
        "h2{margin-top:26px;font-size:22px;line-height:1.25;}"
        "h3{margin-top:18px;font-size:18px;}"
        "p,li{font-size:17px;}"
        "img{max-width:100%;height:auto;border-radius:14px;display:block;margin:14px 0;border:1px solid #1f2a3a;}"
        "a{color:#7dd3fc;text-decoration:none;}a:hover{text-decoration:underline;}"
        ".meta{color:#9fb0c3;font-size:14px;margin:8px 0 14px;}"
        ".quick-answer{background:#0c1624;border:1px solid #223247;border-radius:12px;padding:10px 12px;}"
        ".tag-row{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0 18px;}"
        ".tag-pill{display:inline-block;background:rgba(125,211,252,.16);"
        "border:1px solid rgba(125,211,252,.32);color:#e8eef5;border-radius:999px;"
        "padding:3px 10px;font-size:12px;}"
        ".toc,.related{background:#101a29;border:1px solid #26374b;border-radius:14px;"
        "padding:12px 14px;margin:16px 0;}"
        ".related-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;}"
        ".related-card{background:#0a1320;border:1px solid #1f3148;border-radius:12px;padding:10px;}"
        ".related-card h3{margin:8px 0;}"
        "ul,ol{padding-left:22px;}"
        "small{color:#9fb0c3;}"
        "@media (max-width:760px){.site-header{position:static;}.header-inner{display:block;}.site-nav{margin-top:8px;gap:10px;}.site-subtitle{font-size:12px;}.container{padding-top:14px;}}"
    )
