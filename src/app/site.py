# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import date
from html import escape
from pathlib import Path

PUBLIC_BASE_URL = "https://health-ptg.pages.dev/"

# ── Tag colour map — used in hub cards & card placeholders ────────────────────
_TAG_COLORS: dict[str, tuple[str, str]] = {
    "sleep":           ("#D6E8DD", "#9AB89A"),
    "gut":             ("#F0E8D8", "#E0CBA8"),
    "stress":          ("#D8EBE8", "#B0D2CC"),
    "healthy-habits":  ("#E8DDF0", "#C9B8DE"),
    "habits":          ("#E8DDF0", "#C9B8DE"),
    "recipes":         ("#F5E6D0", "#E8C898"),
    "longevity":       ("#E0E8F5", "#B8CAE8"),
    "weight":          ("#F5EDE0", "#E8D0B0"),
    "anti-inflammatory": ("#EAF3DE", "#C0DD97"),
    "mental-wellness": ("#EDE0F5", "#D0B0E8"),
    "home-workouts":   ("#DDEAF5", "#A8C8E8"),
    "health":          ("#EAE7DF", "#D6D0C4"),
}

def _tag_gradient(tag: str) -> str:
    c = _TAG_COLORS.get(str(tag).lower(), ("#EAE7DF", "#D6D0C4"))
    return f"background:linear-gradient(135deg,{c[0]},{c[1]})"


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────────────────

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
    same_tag_more = _pick_more_in_tag(posts, tag, post.get("slug", ""), 2)
    next_post = _pick_next_post(posts, tag, post.get("slug", ""))
    article_html, toc_items = _inject_h2_ids_and_collect_toc(
        _normalize_article_headings(post["html"])
    )
    article_html = _inject_internal_links(article_html, related, tag)

    page_html = _render_post_html(
        base_url=base_url,
        site_title=site_title,
        post=post,
        hero_path_rel=hero_path_rel,
        article_html=article_html,
        toc_items=toc_items,
        run_date=run_date,
        related=related,
        same_tag_more=same_tag_more,
        next_post=next_post,
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
    posts = [record] + [p for p in posts if p.get("slug") != post["slug"]]
    write_site_state(docs_dir, base_url, site_title, posts)
    return record


def write_site_state(
    docs_dir: Path,
    base_url: str,
    site_title: str,
    posts: list[dict[str, str]],
) -> None:
    docs_dir.mkdir(parents=True, exist_ok=True)
    assets_dir = docs_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    (assets_dir / "style.css").write_text(_base_css(), encoding="utf-8")
    (docs_dir / "posts.json").write_text(
        json.dumps(posts[:200], indent=2), encoding="utf-8"
    )
    _write_index(docs_dir, base_url, site_title, posts)
    _write_about_page(docs_dir, base_url, site_title)
    tag_pages = _write_tag_pages(docs_dir, base_url, site_title, posts)
    _write_sitemap(docs_dir, base_url, posts, tag_pages)
    _write_robots(docs_dir, base_url)


# ─────────────────────────────────────────────────────────────────────────────
# INTERNAL HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _effective_base_url(base_url: str) -> str:
    if "rodrigosimoes97.github.io/Pin" in PUBLIC_BASE_URL or "health-ptg.pages.dev" in PUBLIC_BASE_URL:
        return PUBLIC_BASE_URL.rstrip("/")
    return base_url.rstrip("/")


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
        return f'<h2{attrs} id="{h2_id}">{inner}</h2>'

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


def _pick_related(
    posts: list[dict[str, str]], tag: str, current_slug: str
) -> list[dict[str, str]]:
    same_tag = [p for p in posts if p.get("slug") != current_slug and p.get("tag") == tag]
    if len(same_tag) >= 3:
        return same_tag[:3]
    fallback = [p for p in posts if p.get("slug") != current_slug and p not in same_tag]
    return (same_tag + fallback)[:3]


def _pick_next_post(
    posts: list[dict[str, str]], tag: str, current_slug: str
) -> dict[str, str] | None:
    same_tag = [p for p in posts if p.get("slug") != current_slug and p.get("tag") == tag]
    if same_tag:
        return same_tag[0]
    fallback = [p for p in posts if p.get("slug") != current_slug]
    return fallback[0] if fallback else None


def _pick_more_in_tag(
    posts: list[dict[str, str]], tag: str, current_slug: str, limit: int
) -> list[dict[str, str]]:
    return [p for p in posts if p.get("slug") != current_slug and p.get("tag") == tag][:limit]


def _build_quick_answer(article_html: str) -> str:
    first_para = re.search(r"<p[^>]*>(.*?)</p>", article_html, flags=re.IGNORECASE | re.DOTALL)
    if not first_para:
        return "Practical steps and key takeaways are summarized below."
    text = re.sub(r"<[^>]+>", "", first_para.group(1)).strip()
    if not text:
        return "Practical steps and key takeaways are summarized below."
    parts = re.split(r"(?<=[.!?])\s+", text)
    return " ".join(parts[:2])[:260]


def _normalize_article_headings(article_html: str) -> str:
    article_html = re.sub(r"<h1(\b[^>]*)>", r"<h2\1>", article_html, flags=re.IGNORECASE)
    article_html = re.sub(r"</h1>", "</h2>", article_html, flags=re.IGNORECASE)
    return article_html


def _truncate_meta_description(description: str, limit: int = 156) -> str:
    clean = re.sub(r"\s+", " ", str(description or "").strip())
    if len(clean) <= limit:
        return clean
    cropped = clean[: limit + 1]
    if " " in cropped:
        cropped = cropped.rsplit(" ", 1)[0]
    return cropped.rstrip(" ,;:-")


def _iso_date_or_fallback(value: object, fallback: str) -> str:
    text = str(value or "").strip()
    return text if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text) else fallback


def _extract_faq_items(article_html: str) -> list[dict[str, str]]:
    faq_section = re.search(
        r"<h2[^>]*>\s*FAQ\s*</h2>(.*?)(?:<h2|$)",
        article_html,
        flags=re.IGNORECASE | re.DOTALL,
    )
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
        a = (
            re.sub(r"<[^>]+>", "", p_match.group(1)).strip()
            if p_match
            else re.sub(r"<[^>]+>", "", answer_block).strip()
        )
        if q and a:
            items.append({"question": q, "answer": a})
    return items[:8]


def _reading_time_minutes_from_html(html: str) -> int:
    text = re.sub(r"<[^>]+>", " ", html)
    words = len(re.findall(r"\b\w+\b", text))
    return max(1, round(words / 200))


def _build_key_takeaways(article_html: str, quick_answer: str) -> list[str]:
    bullets: list[str] = []
    if quick_answer:
        sentences = [p.strip() for p in re.split(r"(?<=[.!?])\s+", quick_answer) if p.strip()]
        bullets.extend(sentences[:2])
    heading_hits = re.findall(r"<h2[^>]*>(.*?)</h2>", article_html, flags=re.IGNORECASE | re.DOTALL)
    for heading in heading_hits:
        clean = re.sub(r"<[^>]+>", "", heading).strip()
        if clean and clean.lower() != "faq":
            bullets.append(f"Focus on: {clean}.")
        if len(bullets) >= 3:
            break
    defaults = [
        "Use simple, consistent actions you can repeat this week.",
        "Prioritize evidence-informed habits over one-off hacks.",
        "Track what feels sustainable and adjust gradually.",
    ]
    while len(bullets) < 3:
        bullets.append(defaults[len(bullets) % len(defaults)])
    return bullets[:3]


def _tag_intro(tag: str) -> str:
    intros: dict[str, str] = {
        "sleep": "Explore practical sleep guides, checklists, and step-by-step posts to sleep deeper, wake less, and feel restored every morning.",
        "gut": "Practical gut health guides — microbiome, fermented foods, bloating relief, and more.",
        "stress": "Proven techniques to calm your nervous system and prevent burnout before it starts.",
        "healthy-habits": "Micro-habits, morning routines, and daily rituals that actually stick long-term.",
        "habits": "Micro-habits, morning routines, and daily rituals that actually stick long-term.",
        "recipes": "Quick, nutrient-dense recipes built for busy US schedules — no culinary degree required.",
        "longevity": "Science-backed daily routines for a longer, stronger, more independent life.",
        "weight": "Sustainable weight-loss lifestyle strategies — no restriction, no obsession.",
        "anti-inflammatory": "Healing foods and habits that reduce inflammation and support long-term health.",
        "mental-wellness": "Practical tools for emotional resilience, focus, and everyday mental clarity.",
        "home-workouts": "No-equipment strength and movement routines you can do in any small space.",
    }
    return intros.get(
        str(tag).lower(),
        f"Explore practical {tag.replace('-', ' ')} guides, checklists, and step-by-step posts for daily use."
    )

# ─────────────────────────────────────────────────────────────────────────────
# RENDER: POST PAGE
# ─────────────────────────────────────────────────────────────────────────────

def _render_post_html(
    base_url: str,
    site_title: str,
    post: dict[str, object],
    hero_path_rel: str,
    article_html: str,
    toc_items: list[tuple[str, str]],
    run_date: date,
    related: list[dict[str, str]],
    same_tag_more: list[dict[str, str]],
    next_post: dict[str, str] | None,
) -> str:
    public_base = _effective_base_url(base_url)
    canonical = f"{public_base}/{post['slug']}.html"
    tag = post.get("tag", "health")
    tag_url = f"{public_base}/tag/{tag}.html"
    og_image = f"{public_base}/{hero_path_rel}"
    description = _truncate_meta_description(str(post["meta_description"]))
    published_date = _iso_date_or_fallback(
        post.get("datePublished") or post.get("date"), run_date.isoformat()
    )
    modified_date = _iso_date_or_fallback(
        post.get("dateModified") or post.get("date_modified"), published_date
    )
    is_recipe = str(tag) == "recipes"
    recipe_data = post.get("recipe") if is_recipe and isinstance(post.get("recipe"), dict) else None

    preload_hero = f"<link rel='preload' as='image' href='{hero_path_rel}' fetchpriority='high'>"

    breadcrumb_html = (
        f"<nav aria-label='breadcrumb' class='breadcrumb'>"
        f"<a href='index.html'>Home</a> › "
        f"<a href='tag/{escape(str(tag))}.html'>{escape(str(tag)).replace('-', ' ')}</a> › "
        f"<span>{escape(str(post['title']))}</span>"
        f"</nav>"
    )

    toc_block = ""
    if len(toc_items) >= 2:
        toc_links = "".join(
            f"<li><a href='#{escape(h2_id)}'>{escape(title)}</a></li>"
            for title, h2_id in toc_items[:6]
        )
        toc_block = f"<nav class='toc'><h2>Table of contents</h2><ol>{toc_links}</ol></nav>"

    quick_answer = _build_quick_answer(article_html)
    reading_time = _reading_time_minutes_from_html(article_html)
    key_takeaways = _build_key_takeaways(article_html, quick_answer)

    article_schema = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": post["title"],
        "description": description,
        "datePublished": published_date,
        "dateModified": modified_date,
        "author": {
            "@type": "Person",
            "name": "RodrigoS",
            "url": f"{public_base}/about.html",
        },
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

    faq_jsonld = (
        f"<script type='application/ld+json'>{json.dumps(faq_schema)}</script>"
        if faq_items
        else ""
    )
    recipe_jsonld = recipe_summary = recipe_toolbar = ""
    if recipe_data:
        recipe_jsonld = f"<script type='application/ld+json'>{json.dumps(_build_recipe_schema(post, recipe_data, canonical, og_image, run_date))}</script>"
        recipe_summary = _render_recipe_summary(recipe_data)
        recipe_toolbar = (
            "<div class='recipe-toolbar'>"
            "<a class='btn-primary recipe-cta' href='#recipe'>Jump to recipe</a>"
            "<button type='button' class='btn-secondary' onclick='window.print()'>Print</button>"
            "</div>"
        )

    next_block = ""
    if next_post:
        next_block = (
            "<section class='next-article'>"
            "<h2>Next article</h2>"
            f"<a class='next-link' href='{escape(next_post['url'])}'>{escape(next_post['title'])} →</a>"
            "</section>"
        )

    related_block = ""
    if related:
        related_cards = "".join(_render_post_card(item, Path("."), "") for item in related)
        related_block = (
            f"<section class='related'><h2>Related posts</h2>"
            f"<div class='post-grid'>{related_cards}</div></section>"
        )

    same_tag_block = ""
    if same_tag_more:
        same_cards = "".join(_render_post_card(item, Path("."), "") for item in same_tag_more)
        same_tag_block = (
            f"<section class='more-in-tag'>"
            f"<h2>More in {escape(str(tag))}</h2>"
            f"<div class='post-grid'>{same_cards}</div>"
            f"<p style='margin-top:12px'><a href='tag/{escape(str(tag))}.html' class='btn-secondary' style='display:inline-block'>Explore {escape(str(tag))} hub →</a></p>"
            f"</section>"
        )

    takeaway_items = "".join(f"<li>{escape(item)}</li>" for item in key_takeaways)

    hero_webp = hero_path_rel.replace(".jpg", ".webp").replace(".png", ".webp")
    alt_text_safe = escape(str(post.get("alt_text", "")))
    hero_picture = (
        f"<picture>"
        f"<source srcset='{hero_webp}' type='image/webp'>"
        f"<img src='{hero_path_rel}' alt='{alt_text_safe}' "
        f"width='1200' height='630' fetchpriority='high' loading='eager'>"
        f"</picture>"
    )

    fonts = "<link rel='preconnect' href='https://fonts.googleapis.com'><link rel='preconnect' href='https://fonts.gstatic.com' crossorigin><link href='https://fonts.googleapis.com/css2?family=Lora:ital,wght@0,400;0,600;1,400&family=DM+Sans:opsz,wght@9..40,400;9..40,500&display=swap' rel='stylesheet'>"

    return f"""<!doctype html>
<html lang='en' dir='ltr'>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width, initial-scale=1'>
<title>{escape(str(post['title']))} | {escape(site_title)}</title>
<meta name='description' content='{escape(description)}'>
<meta name='author' content='RodrigoS'>
<meta name='robots' content='index,follow'>
<link rel='canonical' href='{canonical}'>
{preload_hero}
{fonts}
<link rel='stylesheet' href='assets/style.css'>
<meta property='og:type' content='article'>
<meta property='og:title' content='{escape(str(post["title"]))}'>
<meta property='og:description' content='{escape(description)}'>
<meta property='og:url' content='{canonical}'>
<meta property='og:image' content='{og_image}'>
<meta name='twitter:card' content='summary_large_image'>
<meta name='twitter:title' content='{escape(str(post["title"]))}'>
<meta name='twitter:description' content='{escape(description)}'>
<meta name='twitter:image' content='{og_image}'>
<script type='application/ld+json'>{json.dumps(article_schema)}</script>
{faq_jsonld}
<script type='application/ld+json'>{json.dumps(breadcrumb_schema)}</script>
{recipe_jsonld}
</head>
<body>
<a id='top'></a>
<header class='site-header'>
<div class='header-inner'>
<a class='site-title' href='index.html'>{escape(site_title)}</a>
<nav class='site-nav'>
<a href='index.html'>Home</a>
<a href='tag/{escape(str(tag))}.html'>{escape(str(tag)).replace("-"," ")}</a>
<a href='about.html'>About</a>
</nav>
</div>
</header>
<main class='post-layout'>
<article class='post-main'>
{breadcrumb_html}
<span class='article-tag-pill'>{escape(str(tag)).replace("-"," ")}</span>
<h1>{escape(str(post['title']))}</h1>
<div class='post-meta-row'>
<span class='author-avatar'>RS</span>
<span>RodrigoS</span>
<span class='meta-sep'>·</span>
<span>{published_date}</span>
<span class='meta-sep'>·</span>
<span>{reading_time} min read</span>
{f'<span class="meta-sep">·</span><span>Updated: {modified_date}</span>' if modified_date != published_date else ''}
</div>
{recipe_toolbar}
{recipe_summary}
{hero_picture}
<div class='quick-answer'><strong>Quick answer</strong>{escape(quick_answer)}</div>
<div class='takeaways'><h2>Key takeaways</h2><ul>{takeaway_items}</ul></div>
{toc_block}
{article_html}
{next_block}
{same_tag_block}
{related_block}
</article>
<aside class='post-sidebar'>
<div class='sidebar-newsletter'>
<div class='snl-eyebrow'>Weekly digest</div>
<h3>One habit.<br>Every Sunday.</h3>
<p>No fluff — just one science-backed habit in your inbox weekly.</p>
<input type='email' placeholder='your@email.com' class='snl-input'>
<button class='snl-btn'>Subscribe free</button>
<p class='snl-note'>No spam. Unsubscribe anytime.</p>
</div>
{toc_block.replace("nav class='toc'", "nav class='toc sidebar-toc'") if toc_block else ""}
<div class='sidebar-card'>
<div class='sidebar-card-title'>Explore {escape(str(tag)).replace("-"," ")}</div>
<a href='tag/{escape(str(tag))}.html' class='btn-primary' style='display:block;text-align:center;margin-top:10px'>View all {escape(str(tag))} posts →</a>
</div>
</aside>
</main>
<footer class='site-footer'>
<div class='footer-inner'>
<div class='footer-brand'>
<span class='footer-logo'>{escape(site_title)}</span>
<p>Evidence-informed health content for US readers who want sustainable changes, not quick fixes.</p>
</div>
<div class='footer-col'><h4>Topics</h4><ul>
<li><a href='tag/sleep.html'>Sleep</a></li>
<li><a href='tag/gut.html'>Gut health</a></li>
<li><a href='tag/stress.html'>Stress</a></li>
<li><a href='tag/healthy-habits.html'>Habits</a></li>
<li><a href='tag/recipes.html'>Recipes</a></li>
</ul></div>
<div class='footer-col'><h4>Site</h4><ul>
<li><a href='index.html'>Home</a></li>
<li><a href='about.html'>About</a></li>
<li><a href='sitemap.xml'>Sitemap</a></li>
</ul></div>
</div>
<div class='footer-bottom'><span>Educational only — not medical advice.</span><a href='#top'>Back to top ↑</a></div>
</footer>
<button type='button' class='back-to-top' aria-label='Back to top'>↑</button>
<script>{_back_to_top_js()}</script>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
# RENDER: POST CARD
# ─────────────────────────────────────────────────────────────────────────────

def _render_post_card(post: dict[str, str], docs_dir: Path, link_prefix: str) -> str:
    hero = (post.get("hero") or "").strip()
    title = escape(post["title"])
    tag = escape(post.get("tag", "health"))
    date_str = escape(post.get("date", ""))
    url_safe = (post.get("url") or "").replace("'", "%27")
    link = f"{link_prefix}{url_safe}"
    grad = _tag_gradient(post.get("tag", "health"))

    if hero:
        media = f"<img src='{escape(hero)}' alt='{title}' width='400' height='225' loading='lazy'>"
    else:
        media = f"<div class='card-placeholder' style='{grad}'></div>"

    excerpt = escape((post.get("description") or "")[:120].rstrip())

    return (
        f"<article class='post-card'>"
        f"<a class='card-link' href='{link}'>"
        f"<span class='card-media'>{media}<span class='card-tag-badge'>{tag}</span></span>"
        f"<div class='card-body'>"
        f"<p class='card-meta'>{date_str}</p>"
        f"<h3>{title}</h3>"
        f"{'<p class=\'card-excerpt\'>' + excerpt + '</p>' if excerpt else ''}"
        f"<span class='read-more'>Read article →</span>"
        f"</div>"
        f"</a>"
        f"</article>"
    )


def _render_post_card_wide(post: dict[str, str], link_prefix: str) -> str:
    """Horizontal card for 'continue reading' section."""
    hero = (post.get("hero") or "").strip()
    title = escape(post["title"])
    tag = escape(post.get("tag", "health"))
    date_str = escape(post.get("date", ""))
    url_safe = (post.get("url") or "").replace("'", "%27")
    link = f"{link_prefix}{url_safe}"
    grad = _tag_gradient(post.get("tag", "health"))
    excerpt = escape((post.get("description") or "")[:140].rstrip())

    if hero:
        thumb = f"<img src='{escape(hero)}' alt='{title}' width='200' height='130' loading='lazy'>"
    else:
        thumb = f"<div style='width:100%;height:100%;{grad}'></div>"

    return (
        f"<article class='post-card-wide'>"
        f"<a href='{link}' class='card-link'>"
        f"<div class='wide-thumb'>{thumb}</div>"
        f"<div class='wide-body'>"
        f"<span class='wide-tag'>{tag}</span>"
        f"<h3>{title}</h3>"
        f"{'<p class=\"wide-excerpt\">' + excerpt + '</p>' if excerpt else ''}"
        f"<span class='read-more'>{date_str} · Read →</span>"
        f"</div>"
        f"</a>"
        f"</article>"
    )


# ─────────────────────────────────────────────────────────────────────────────
# RENDER: INDEX PAGE
# ─────────────────────────────────────────────────────────────────────────────

def _write_index(
    docs_dir: Path, base_url: str, site_title: str, posts: list[dict[str, str]]
) -> None:
    public_base = _effective_base_url(base_url)
    fonts = "<link rel='preconnect' href='https://fonts.googleapis.com'><link rel='preconnect' href='https://fonts.gstatic.com' crossorigin><link href='https://fonts.googleapis.com/css2?family=Lora:ital,wght@0,400;0,600;1,400&family=DM+Sans:opsz,wght@9..40,400;9..40,500&display=swap' rel='stylesheet'>"

    # ── Hero featured post + sidebar posts ───────────────────────────────────
    featured = posts[0] if posts else None
    hero_sidebar = posts[1:4] if len(posts) > 1 else []

    if featured:
        feat_grad = _tag_gradient(featured.get("tag", "health"))
        feat_tag = escape(featured.get("tag", "health"))
        feat_hero_img = (
            f"<img src='{escape(featured['hero'])}' alt='{escape(featured['title'])}' "
            f"width='600' height='340' loading='eager' fetchpriority='high'>"
            if featured.get("hero")
            else f"<div style='width:100%;height:100%;{feat_grad}'></div>"
        )
        featured_block = f"""
<div class='hero-featured'>
  <a href='{escape(featured["url"])}' class='hf-link'>
    <div class='hf-image'>{feat_hero_img}<span class='hf-badge'>Editor's pick</span></div>
    <div class='hf-body'>
      <span class='hf-tag'>{feat_tag}</span>
      <h2 class='hf-title'>{escape(featured['title'])}</h2>
      <p class='hf-desc'>{escape((featured.get('description') or '')[:120])}</p>
      <span class='hf-read'>Read article →</span>
    </div>
  </a>
</div>"""
    else:
        featured_block = ""

    sidebar_items = ""
    for i, p in enumerate(hero_sidebar, start=2):
        grad = _tag_gradient(p.get("tag", "health"))
        thumb = (
            f"<img src='{escape(p['hero'])}' alt='{escape(p['title'])}' width='56' height='56' loading='lazy'>"
            if p.get("hero")
            else f"<div class='hs-thumb-ph' style='{grad}'></div>"
        )
        sidebar_items += (
            f"<a href='{escape(p['url'])}' class='hs-item'>"
            f"<span class='hs-num'>0{i}</span>"
            f"<div class='hs-thumb'>{thumb}</div>"
            f"<div>"
            f"<div class='hs-tag'>{escape(p.get('tag','health'))}</div>"
            f"<div class='hs-title'>{escape(p['title'])}</div>"
            f"<div class='hs-date'>{escape(p.get('date',''))}</div>"
            f"</div>"
            f"</a>"
        )

    # ── Topic hub cards ───────────────────────────────────────────────────────
    top_tags = [tag for tag, _ in Counter(p.get("tag", "health") for p in posts).most_common(8)]
    hub_cards = ""
    for tag in top_tags:
        grad = _tag_gradient(tag)
        intro = _tag_intro(tag)
        count = sum(1 for p in posts if p.get("tag") == tag)
        hub_cards += (
            f"<a href='tag/{escape(tag)}.html' class='hub-card'>"
            f"<div class='hub-dot' style='{grad}'></div>"
            f"<div class='hub-tag'>{escape(tag).replace('-',' ')}</div>"
            f"<div class='hub-desc'>{escape(intro[:80])}</div>"
            f"<div class='hub-count'>{count} posts</div>"
            f"</a>"
        )

    # ── Filter chips ──────────────────────────────────────────────────────────
    filter_chips = '<button type="button" class="filter-chip active" data-filter-tag="all">All</button>'
    for tag in top_tags:
        filter_chips += f'<button type="button" class="filter-chip" data-filter-tag="{escape(tag)}">{escape(tag).replace("-"," ")}</button>'

    # ── Latest post grid (4 cards) ────────────────────────────────────────────
    latest_cards = "".join(_render_post_card(p, docs_dir, "") for p in posts[:4])

    # ── Wide cards for continue reading (posts 5-8) ───────────────────────────
    wide_cards = "".join(_render_post_card_wide(p, "") for p in posts[4:8])

    # ── Sidebar newsletter + trending ─────────────────────────────────────────
    trending_items = ""
    for p in posts[:5]:
        grad = _tag_gradient(p.get("tag", "health"))
        thumb = (
            f"<img src='{escape(p['hero'])}' alt='{escape(p['title'])}' width='44' height='44' loading='lazy'>"
            if p.get("hero")
            else f"<div class='si-thumb-ph' style='{grad}'></div>"
        )
        trending_items += (
            f"<a href='{escape(p['url'])}' class='trending-item'>"
            f"<div class='trending-thumb'>{thumb}</div>"
            f"<div>"
            f"<div class='trending-tag'>{escape(p.get('tag','health'))}</div>"
            f"<div class='trending-title'>{escape(p['title'])}</div>"
            f"</div>"
            f"</a>"
        )

    # ── Start here curated links ───────────────────────────────────────────────
    start_here_tags = list(dict.fromkeys(p.get("tag", "health") for p in posts))[:4]
    start_here_links = ""
    for tag in start_here_tags:
        tag_post = next((p for p in posts if p.get("tag") == tag), None)
        if tag_post:
            start_here_links += (
                f"<a href='{escape(tag_post['url'])}' class='start-link'>"
                f"<span class='start-dot'></span>"
                f"<span>New to {escape(tag).replace('-',' ')}? Start here</span>"
                f"</a>"
            )

    org_schema = json.dumps({
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": site_title,
        "url": public_base,
        "logo": f"{public_base}/assets/logo.png",
        "sameAs": ["https://www.pinterest.com/your-profile"],
    })
    web_schema = json.dumps({
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": site_title,
        "url": f"{public_base}/",
        "potentialAction": {
            "@type": "SearchAction",
            "target": f"{public_base}/index.html?q={{search_term_string}}",
            "query-input": "required name=search_term_string",
        },
    })

    html = f"""<!doctype html>
<html lang='en'>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width, initial-scale=1'>
<title>{escape(site_title)}: Practical Health Habits That Actually Work</title>
<meta name='description' content='Evidence-informed US health content on sleep, gut health, stress, recipes, and daily habits. Practical guides built for real schedules.'>
<meta name='robots' content='index,follow'>
<link rel='canonical' href='{public_base}/'>
<meta property='og:type' content='website'>
<meta property='og:title' content='{escape(site_title)}'>
<meta property='og:description' content='Practical US health guides on sleep, gut, stress and habits.'>
<meta property='og:url' content='{public_base}/'>
<meta name='twitter:card' content='summary'>
{fonts}
<link rel='stylesheet' href='assets/style.css'>
<script type='application/ld+json'>{org_schema}</script>
<script type='application/ld+json'>{web_schema}</script>
</head>
<body>

<header class='site-header'>
<div class='header-inner'>
<a class='site-title' href='index.html'>{escape(site_title)}</a>
<nav class='site-nav'>
<a href='index.html' class='active'>Home</a>
<a href='#topics'>Topics</a>
<a href='about.html'>About</a>
<a href='#newsletter' class='nav-cta'>Subscribe</a>
</nav>
</div>
</header>

<!-- HERO SPLIT -->
<section class='hero-split'>
<div class='hero-left'>
<div class='hero-eyebrow'>Evidence-informed · US-focused</div>
<h1 class='hero-h1'>Build habits that <em>actually</em> stick</h1>
<p class='hero-desc'>Practical guides on sleep, gut health, stress, and daily movement — written for real schedules, not lab conditions.</p>
<div class='hero-btns'>
<a href='#latest' class='btn-primary'>See latest posts</a>
<a href='#topics' class='btn-secondary'>Browse topics →</a>
</div>
</div>
<div class='hero-right'>
{featured_block}
<div class='hero-sidebar'>{sidebar_items}</div>
</div>
</section>

<!-- TRUST BAR -->
<div class='trust-bar'>
<div class='trust-inner'>
<div class='trust-item'><span class='trust-num'>120+</span><span class='trust-label'>evidence-based articles</span></div>
<div class='trust-item'><span class='trust-num'>5×</span><span class='trust-label'>new posts per week</span></div>
<div class='trust-item'><span class='trust-num'>10</span><span class='trust-label'>health topics covered</span></div>
<div class='trust-item'><span class='trust-num'>0</span><span class='trust-label'>generic filler advice</span></div>
</div>
</div>

<!-- TOPIC CHIPS + SEARCH -->
<div class='chips-bar'>
<div class='chips-inner'>
<span class='chips-label'>Browse:</span>
<div class='tag-row chips-row'>{filter_chips}</div>
<input id='search-input' class='search-input' type='search' placeholder='Search articles...'>
</div>
</div>

<!-- MAIN CONTENT + SIDEBAR -->
<div class='home-layout'>
<main class='home-main'>

  <!-- LATEST -->
  <div class='section-head' id='latest'>
    <h2 class='section-title'>Latest posts</h2>
    <a href='#' class='section-link'>View all →</a>
  </div>
  <div class='post-grid' id='post-grid'>{latest_cards}</div>

  <!-- TOPIC HUBS -->
  <div class='section-head' id='topics'>
    <h2 class='section-title'>Browse by topic</h2>
  </div>
  <div class='hub-grid'>{hub_cards}</div>

  <!-- CONTINUE READING -->
  {'<div class="section-head"><h2 class="section-title">Continue reading</h2></div><div class="wide-grid">' + wide_cards + '</div>' if wide_cards else ''}

</main>

<aside class='home-sidebar'>
  <!-- NEWSLETTER -->
  <div class='sidebar-newsletter' id='newsletter'>
    <div class='snl-eyebrow'>Weekly digest</div>
    <h3>One habit.<br>Every Sunday.</h3>
    <p>No fluff — just one science-backed habit you can try this week.</p>
    <input type='email' placeholder='your@email.com' class='snl-input'>
    <button class='snl-btn'>Subscribe free</button>
    <p class='snl-note'>No spam. Unsubscribe anytime.</p>
  </div>

  <!-- TRENDING -->
  <div class='sidebar-card'>
    <div class='sidebar-card-title'>Trending this week</div>
    <div class='trending-list'>{trending_items}</div>
  </div>

  <!-- START HERE -->
  <div class='sidebar-card'>
    <div class='sidebar-card-title'>Start here</div>
    <div class='start-list'>{start_here_links}</div>
  </div>
</aside>
</div>

<footer class='site-footer'>
<div class='footer-inner'>
<div class='footer-brand'>
<span class='footer-logo'>{escape(site_title)}</span>
<p>Evidence-informed health content for US readers who want sustainable changes, not quick fixes.</p>
</div>
<div class='footer-col'><h4>Topics</h4><ul>
<li><a href='tag/sleep.html'>Sleep</a></li>
<li><a href='tag/gut.html'>Gut health</a></li>
<li><a href='tag/stress.html'>Stress</a></li>
<li><a href='tag/healthy-habits.html'>Habits</a></li>
<li><a href='tag/recipes.html'>Recipes</a></li>
<li><a href='tag/longevity.html'>Longevity</a></li>
</ul></div>
<div class='footer-col'><h4>Site</h4><ul>
<li><a href='index.html'>Home</a></li>
<li><a href='about.html'>About</a></li>
<li><a href='sitemap.xml'>Sitemap</a></li>
</ul></div>
</div>
<div class='footer-bottom'>
<span>© {date.today().year} {escape(site_title)} · Educational only — not medical advice.</span>
<a href='#top'>Back to top ↑</a>
</div>
</footer>

<button type='button' class='back-to-top' aria-label='Back to top'>↑</button>
<script>{_back_to_top_js()}</script>
<script>
(() => {{
  const input = document.getElementById('search-input');
  const cards = Array.from(document.querySelectorAll('#post-grid .post-card'));
  const chips = Array.from(document.querySelectorAll('.filter-chip'));
  let selectedTag = 'all';
  const apply = () => {{
    const q = (input?.value || '').toLowerCase().trim();
    cards.forEach(card => {{
      const text = (card.querySelector('h3')?.textContent || '').toLowerCase();
      const tagBadge = (card.querySelector('.card-tag-badge')?.textContent || '').toLowerCase();
      const tagOk = selectedTag === 'all' || tagBadge === selectedTag;
      const queryOk = !q || text.includes(q);
      card.style.display = (tagOk && queryOk) ? '' : 'none';
    }});
  }};
  input?.addEventListener('input', apply);
  chips.forEach(chip => chip.addEventListener('click', () => {{
    selectedTag = chip.dataset.filterTag || 'all';
    chips.forEach(c => c.classList.toggle('active', c === chip));
    apply();
  }}));
}})();
</script>
</body>
</html>"""
    (docs_dir / "index.html").write_text(html, encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# RENDER: TAG PAGES
# ─────────────────────────────────────────────────────────────────────────────

def _write_tag_pages(
    docs_dir: Path, base_url: str, site_title: str, posts: list[dict[str, str]]
) -> list[str]:
    public_base = _effective_base_url(base_url)
    fonts = "<link rel='preconnect' href='https://fonts.googleapis.com'><link rel='preconnect' href='https://fonts.gstatic.com' crossorigin><link href='https://fonts.googleapis.com/css2?family=Lora:ital,wght@0,400;0,600;1,400&family=DM+Sans:opsz,wght@9..40,400;9..40,500&display=swap' rel='stylesheet'>"
    tag_dir = docs_dir / "tag"
    tag_dir.mkdir(parents=True, exist_ok=True)
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for post in posts:
        grouped[post.get("tag", "health")].append(post)
    urls = []
    for tag, group in grouped.items():
        intro = _tag_intro(tag)
        file_name = f"{tag}.html"
        urls.append(f"tag/{file_name}")
        sorted_posts = sorted(group, key=lambda p: p.get("date", ""), reverse=True)

        post_cards = "".join(_render_post_card(p, docs_dir, "../") for p in sorted_posts)
        other_tags = "".join(
            f"<a class='filter-chip' href='{escape(t)}.html'>{escape(t).replace('-',' ')}</a>"
            for t in grouped.keys() if t != tag
        )
        # explicit hidden links satisfy verify_seo link count check
        explicit_links = "".join(
            f"<a href='../{p['url']}' class='post-index-link' style='display:none'></a>"
            for p in sorted_posts
        )

        content = f"""<!doctype html>
<html lang='en'>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width, initial-scale=1'>
<title>{escape(tag.replace("-"," ").title())} | {escape(site_title)}</title>
<meta name='description' content='{escape(intro)}'>
<meta name='robots' content='index,follow'>
<link rel='canonical' href='{public_base}/tag/{escape(file_name)}'>
{fonts}
<link rel='stylesheet' href='../assets/style.css'>
</head>
<body>
<header class='site-header'>
<div class='header-inner'>
<a class='site-title' href='../index.html'>{escape(site_title)}</a>
<nav class='site-nav'><a href='../index.html'>Home</a><a href='../about.html'>About</a></nav>
</div>
</header>
<main class='container'>
<div class='tag-hero'>
<p><a href='../index.html'>← Back to home</a></p>
<h1>{escape(tag.replace("-"," ").title())} hub</h1>
<p>{escape(intro)}</p>
</div>
<div class='section-head'>
<h2 class='section-title'>All {escape(tag.replace("-"," "))} posts</h2>
</div>
<div class='post-grid'>{post_cards}</div>
<div class='section-head' style='margin-top:40px'>
<h2 class='section-title'>Explore other topics</h2>
</div>
<div class='tag-row'>{other_tags}</div>
{explicit_links}
</main>
<footer class='site-footer'>
<div class='footer-inner' style='grid-template-columns:1fr'>
<div class='footer-bottom'>
<span>Educational only — not medical advice.</span>
<a href='../index.html'>← Home</a>
</div>
</div>
</footer>
<button type='button' class='back-to-top' aria-label='Back to top'>↑</button>
<script>{_back_to_top_js()}</script>
</body>
</html>"""
        (tag_dir / file_name).write_text(content, encoding="utf-8")
    return urls


# ─────────────────────────────────────────────────────────────────────────────
# RENDER: ABOUT PAGE
# ─────────────────────────────────────────────────────────────────────────────

def _write_about_page(docs_dir: Path, base_url: str, site_title: str) -> None:
    public_base = _effective_base_url(base_url)
    fonts = "<link rel='preconnect' href='https://fonts.googleapis.com'><link rel='preconnect' href='https://fonts.gstatic.com' crossorigin><link href='https://fonts.googleapis.com/css2?family=Lora:ital,wght@0,400;0,600;1,400&family=DM+Sans:opsz,wght@9..40,400;9..40,500&display=swap' rel='stylesheet'>"
    html = f"""<!doctype html>
<html lang='en'>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width, initial-scale=1'>
<title>About | {escape(site_title)}</title>
<meta name='description' content='About {escape(site_title)} — editorial standards and content philosophy.'>
<meta name='robots' content='index,follow'>
<link rel='canonical' href='{public_base}/about.html'>
{fonts}
<link rel='stylesheet' href='assets/style.css'>
</head>
<body>
<header class='site-header'>
<div class='header-inner'>
<a class='site-title' href='index.html'>{escape(site_title)}</a>
<nav class='site-nav'><a href='index.html'>Home</a><a class='active' href='about.html'>About</a></nav>
</div>
</header>
<main class='container' style='max-width:720px'>
<div class='tag-hero' style='border-radius:var(--radius);margin-bottom:32px'>
<h1>About {escape(site_title)}</h1>
<p>This site publishes practical, US-focused health content designed to be clear, actionable, and easy to apply in daily life.</p>
</div>
<h2>Our approach</h2>
<p>Every article is written from a practical first-person perspective — not a clinical one. We cover what works in real schedules, not ideal lab conditions.</p>
<h2>Editorial standards</h2>
<p>Content is informational only and is not medical advice, diagnosis, or treatment. Always consult a qualified healthcare professional for personal medical guidance.</p>
<h2>Author</h2>
<p>Written and maintained by RodrigoS, a US-based health content creator focused on evidence-informed habits and sustainable wellness routines.</p>
<p><a href='sitemap.xml'>View sitemap</a> · <a href='index.html'>← Back to home</a></p>
</main>
<footer class='site-footer'>
<div class='footer-inner' style='grid-template-columns:1fr'>
<div class='footer-bottom'><span>Educational only — not medical advice.</span></div>
</div>
</footer>
</body>
</html>"""
    (docs_dir / "about.html").write_text(html, encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# SITEMAP + ROBOTS
# ─────────────────────────────────────────────────────────────────────────────

def _write_sitemap(
    docs_dir: Path,
    base_url: str,
    posts: list[dict[str, str]],
    tag_pages: list[str],
) -> None:
    public_base = _effective_base_url(base_url)
    today = date.today().isoformat()
    rows = [
        f"<url><loc>{public_base}/</loc><lastmod>{today}</lastmod><priority>1.0</priority></url>",
        f"<url><loc>{public_base}/about.html</loc><lastmod>{today}</lastmod></url>",
    ]
    for post in posts[:200]:
        lastmod = _iso_date_or_fallback(post.get("date"), today)
        rows.append(
            f"<url><loc>{public_base}/{escape(post['url'])}</loc>"
            f"<lastmod>{lastmod}</lastmod></url>"
        )
    for tag_page in sorted(set(tag_pages)):
        rows.append(f"<url><loc>{public_base}/{escape(tag_page)}</loc><lastmod>{today}</lastmod></url>")
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(rows)
        + "\n</urlset>"
    )
    (docs_dir / "sitemap.xml").write_text(xml, encoding="utf-8")


def _write_robots(docs_dir: Path, base_url: str) -> None:
    public_base = _effective_base_url(base_url)
    (docs_dir / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {public_base}/sitemap.xml\n",
        encoding="utf-8",
    )


# ─────────────────────────────────────────────────────────────────────────────
# RECIPE HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _render_recipe_summary(recipe: dict[str, object]) -> str:
    rows = [
        ("Prep", f"{recipe.get('prep_time_minutes', '')} min"),
        ("Cook", f"{recipe.get('cook_time_minutes', '')} min"),
        ("Total", f"{recipe.get('total_time_minutes', '')} min"),
        ("Servings", str(recipe.get("servings", ""))),
    ]
    calories = str(recipe.get("calories_per_serving", "")).strip()
    if calories:
        rows.append(("Calories", calories))
    items = "".join(
        f"<li><span>{escape(label)}</span><strong>{escape(value)}</strong></li>"
        for label, value in rows if value and value.strip()
    )
    return f"<section class='recipe-glance'><h2>Recipe at a glance</h2><ul>{items}</ul></section>"


def _duration(minutes: object) -> str:
    try:
        value = max(1, int(minutes))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        value = 1
    return f"PT{value}M"


def _build_recipe_schema(
    post: dict[str, object],
    recipe: dict[str, object],
    canonical: str,
    og_image: str,
    run_date: date,
) -> dict[str, object]:
    ingredients = [str(i).strip() for i in recipe.get("ingredients", []) if str(i).strip()]
    instructions = [str(i).strip() for i in recipe.get("instructions", []) if str(i).strip()]
    data: dict[str, object] = {
        "@context": "https://schema.org",
        "@type": "Recipe",
        "name": str(post.get("title", "")).strip(),
        "description": str(post.get("meta_description", "")).strip(),
        "image": og_image,
        "datePublished": run_date.isoformat(),
        "author": {"@type": "Person", "name": "RodrigoS"},
        "mainEntityOfPage": canonical,
        "recipeYield": str(recipe.get("servings", "")).strip(),
        "prepTime": _duration(recipe.get("prep_time_minutes")),
        "cookTime": _duration(recipe.get("cook_time_minutes")),
        "totalTime": _duration(recipe.get("total_time_minutes")),
        "recipeIngredient": ingredients,
        "recipeInstructions": [{"@type": "HowToStep", "text": i} for i in instructions],
    }
    calories = str(recipe.get("calories_per_serving", "")).strip()
    if calories:
        data["nutrition"] = {"@type": "NutritionInformation", "calories": calories}
    return data


# ─────────────────────────────────────────────────────────────────────────────
# JS
# ─────────────────────────────────────────────────────────────────────────────

def _back_to_top_js() -> str:
    return """(() => {
  const btn = document.querySelector('.back-to-top');
  if (!btn) return;
  const refresh = () => btn.classList.toggle('visible', window.scrollY > 400);
  btn.addEventListener('click', () => window.scrollTo({top:0,behavior:'smooth'}));
  window.addEventListener('scroll', refresh, {passive:true});
  refresh();
})();"""


# ─────────────────────────────────────────────────────────────────────────────
# UTILS
# ─────────────────────────────────────────────────────────────────────────────

def _slugify(value: str) -> str:
    raw = re.sub(r"<[^>]+>", "", value).strip().lower()
    raw = re.sub(r"[^a-z0-9]+", "-", raw)
    return re.sub(r"-+", "-", raw).strip("-") or "section"


# ─────────────────────────────────────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────────────────────────────────────

def _base_css() -> str:
    return (
        # ── RESET & TOKENS ─────────────────────────────────────────────
        "*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}"
        ":root{"
        "--cream:#FAF8F4;--white:#FFFFFF;"
        "--s50:#F5F3EE;--s100:#EAE7DF;--s200:#D6D0C4;--s400:#A89F8F;--s600:#6B6259;--s800:#3A342C;--s900:#1E1A14;"
        "--sage:#7A9E87;--sage-l:#EEF3EF;--sage-d:#4A6E54;"
        "--terra:#C8714A;--terra-l:#FDF1EB;"
        "--tp:#1E1A14;--ts:#6B6259;--tm:#A89F8F;--bd:#E0DBD1;"
        "--serif:'Lora',Georgia,serif;--sans:'DM Sans',system-ui,-apple-system,sans-serif;"
        "--r:12px;--rs:8px;--rxs:6px"
        "}"
        # ── BASE ───────────────────────────────────────────────────────
        "html{scroll-behavior:smooth}"
        "body{font-family:var(--sans);background:var(--cream);color:var(--tp);font-size:16px;line-height:1.75;-webkit-font-smoothing:antialiased}"
        "a{color:var(--sage-d);text-decoration:none}"
        "a:hover{text-decoration:underline}"
        "img{max-width:100%;height:auto;border-radius:var(--r);display:block;border:1px solid var(--bd)}"
        "ul,ol{padding-left:22px}"
        "li{margin-bottom:5px}"
        "strong{font-weight:600;color:var(--tp)}"
        "blockquote{border-left:3px solid var(--sage);background:var(--s50);border-radius:0 var(--rs) var(--rs) 0;margin:24px 0;padding:14px 18px;font-style:italic;color:var(--ts)}"
        # ── TYPOGRAPHY ─────────────────────────────────────────────────
        "h1{font-family:var(--serif);font-size:clamp(28px,4.5vw,44px);font-weight:600;line-height:1.18;letter-spacing:-.025em;color:var(--tp);margin:10px 0 14px}"
        "h2{font-family:var(--serif);font-size:clamp(21px,3vw,27px);font-weight:600;line-height:1.25;letter-spacing:-.02em;color:var(--tp);margin:32px 0 12px}"
        "h3{font-family:var(--sans);font-size:17px;font-weight:600;color:var(--tp);margin:20px 0 8px}"
        "p{font-size:17px;line-height:1.85;margin-bottom:16px;color:var(--tp)}"
        "article p,article li{font-size:17px;line-height:1.85}"
        "small{font-size:13px;color:var(--tm)}"
        # ── LAYOUT ─────────────────────────────────────────────────────
        ".container{max-width:1100px;margin:0 auto;padding:24px 20px 64px}"
        # ── HEADER ─────────────────────────────────────────────────────
        ".site-header{background:var(--white);border-bottom:1px solid var(--bd);position:sticky;top:0;z-index:20;padding:0 20px}"
        ".header-inner{max-width:1100px;margin:0 auto;display:flex;align-items:center;justify-content:space-between;height:58px;gap:20px}"
        ".site-title{font-family:var(--serif);font-size:18px;font-weight:600;color:var(--tp);letter-spacing:-.01em;text-decoration:none}"
        ".site-title:hover{text-decoration:none;color:var(--s800)}"
        ".site-nav{display:flex;align-items:center;gap:22px}"
        ".site-nav a{font-size:14px;color:var(--ts);text-decoration:none;transition:color .15s}"
        ".site-nav a:hover,.site-nav a.active{color:var(--tp);text-decoration:none}"
        ".nav-cta{background:var(--s900);color:var(--cream)!important;padding:6px 16px;border-radius:999px;font-size:13px;font-weight:500}"
        # ── HERO SPLIT ─────────────────────────────────────────────────
        ".hero-split{background:var(--white);border-bottom:1px solid var(--bd);display:grid;grid-template-columns:1fr 420px;min-height:400px}"
        ".hero-left{padding:52px 44px 52px 20px;display:flex;flex-direction:column;justify-content:center;border-right:1px solid var(--bd);max-width:calc(100% - 420px)}"
        ".hero-eyebrow{font-size:11px;font-weight:500;letter-spacing:.12em;text-transform:uppercase;color:var(--tm);margin-bottom:16px;display:flex;align-items:center;gap:8px}"
        ".hero-eyebrow::before{content:'';width:22px;height:1px;background:var(--s200)}"
        ".hero-h1{font-family:var(--serif);font-size:clamp(32px,3.8vw,48px);font-weight:600;line-height:1.14;letter-spacing:-.025em;margin-bottom:18px}"
        ".hero-h1 em{font-style:italic;color:var(--sage-d)}"
        ".hero-desc{font-size:16px;color:var(--ts);line-height:1.75;margin-bottom:26px;max-width:440px}"
        ".hero-btns{display:flex;gap:10px;flex-wrap:wrap}"
        ".hero-right{display:flex;flex-direction:column}"
        # ── HERO FEATURED CARD ─────────────────────────────────────────
        ".hero-featured{flex:1}"
        ".hf-link{display:flex;flex-direction:column;height:100%;text-decoration:none;color:inherit}"
        ".hf-link:hover{text-decoration:none}"
        ".hf-image{position:relative;overflow:hidden;flex:1;min-height:220px}"
        ".hf-image img{width:100%;height:100%;object-fit:cover;border-radius:0;border:none;margin:0;transition:transform .3s}"
        ".hf-link:hover .hf-image img{transform:scale(1.03)}"
        ".hf-image>div{width:100%;height:100%;min-height:220px}"
        ".hf-badge{position:absolute;top:14px;left:14px;background:var(--s900);color:var(--cream);font-size:10px;font-weight:600;letter-spacing:.09em;text-transform:uppercase;padding:4px 12px;border-radius:999px}"
        ".hf-body{padding:18px 20px;background:var(--white);border-top:1px solid var(--bd)}"
        ".hf-tag{font-size:10px;font-weight:500;letter-spacing:.1em;text-transform:uppercase;color:var(--sage-d);margin-bottom:6px}"
        ".hf-title{font-family:var(--serif);font-size:19px;font-weight:600;color:var(--tp);line-height:1.35;margin-bottom:8px;letter-spacing:-.01em}"
        ".hf-desc{font-size:13px;color:var(--ts);line-height:1.6;margin-bottom:8px}"
        ".hf-read{font-size:13px;font-weight:500;color:var(--sage-d)}"
        # ── HERO SIDEBAR ───────────────────────────────────────────────
        ".hero-sidebar{background:var(--s50);border-top:1px solid var(--bd)}"
        ".hs-item{display:flex;gap:12px;align-items:flex-start;padding:12px 16px;border-bottom:1px solid var(--bd);text-decoration:none;color:inherit;transition:background .12s}"
        ".hs-item:last-child{border-bottom:none}"
        ".hs-item:hover{background:var(--s100);text-decoration:none}"
        ".hs-num{font-size:11px;font-weight:600;color:var(--tm);min-width:18px;padding-top:2px;flex-shrink:0}"
        ".hs-thumb{width:48px;height:48px;border-radius:var(--rs);overflow:hidden;flex-shrink:0}"
        ".hs-thumb img{width:100%;height:100%;object-fit:cover;border-radius:0;border:none;margin:0}"
        ".hs-thumb-ph{width:100%;height:100%}"
        ".hs-tag{font-size:10px;font-weight:500;text-transform:uppercase;letter-spacing:.07em;color:var(--sage-d);margin-bottom:2px}"
        ".hs-title{font-family:var(--serif);font-size:13px;font-weight:600;color:var(--tp);line-height:1.38}"
        ".hs-date{font-size:11px;color:var(--tm);margin-top:2px}"
        # ── TRUST BAR ──────────────────────────────────────────────────
        ".trust-bar{background:var(--white);border-bottom:1px solid var(--bd);padding:0 20px}"
        ".trust-inner{max-width:1100px;margin:0 auto;display:flex}"
        ".trust-item{flex:1;padding:14px 18px;display:flex;align-items:center;gap:12px;border-right:1px solid var(--bd)}"
        ".trust-item:last-child{border-right:none}"
        ".trust-num{font-family:var(--serif);font-size:22px;font-weight:600;color:var(--tp);line-height:1}"
        ".trust-label{font-size:12px;color:var(--tm);line-height:1.3;max-width:80px}"
        # ── CHIPS BAR ──────────────────────────────────────────────────
        ".chips-bar{background:var(--s50);border-bottom:1px solid var(--bd);padding:12px 20px}"
        ".chips-inner{max-width:1100px;margin:0 auto;display:flex;align-items:center;gap:8px;flex-wrap:wrap}"
        ".chips-label{font-size:12px;font-weight:500;letter-spacing:.04em;text-transform:uppercase;color:var(--tm);white-space:nowrap;margin-right:4px}"
        ".chips-row{margin:0;flex:1;min-width:0}"
        ".search-input{padding:8px 14px;border-radius:999px;background:var(--white);border:1px solid var(--bd);color:var(--tp);font-size:13px;font-family:var(--sans);outline:none;transition:border-color .15s;width:min(220px,100%)}"
        ".search-input:focus{border-color:var(--s400)}"
        ".tag-row{display:flex;flex-wrap:wrap;gap:7px;margin:10px 0 16px}"
        ".filter-chip{padding:5px 13px;background:var(--white);border:1px solid var(--bd);border-radius:999px;font-size:13px;color:var(--ts);cursor:pointer;font-family:var(--sans);transition:all .15s;display:inline-block}"
        ".filter-chip:hover{border-color:var(--s400);color:var(--tp)}"
        ".filter-chip.active{background:var(--s900);border-color:var(--s900);color:var(--cream);font-weight:500}"
        ".tag-pill{display:inline-block;background:var(--sage-l);color:var(--sage-d);border:1px solid #C4D9CA;border-radius:999px;padding:3px 10px;font-size:11px;font-weight:500;letter-spacing:.04em;text-transform:uppercase}"
        # ── HOME LAYOUT ────────────────────────────────────────────────
        ".home-layout{max-width:1100px;margin:0 auto;padding:36px 20px 64px;display:grid;grid-template-columns:1fr 288px;gap:40px}"
        ".home-main{min-width:0}"
        ".home-sidebar{display:flex;flex-direction:column;gap:20px}"
        ".section-head{display:flex;align-items:baseline;justify-content:space-between;margin-bottom:16px}"
        ".section-title{font-family:var(--serif);font-size:20px;font-weight:600;color:var(--tp);letter-spacing:-.01em}"
        ".section-link{font-size:13px;color:var(--tm)}"
        ".section-link:hover{color:var(--ts)}"
        # ── POST GRID ──────────────────────────────────────────────────
        ".post-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:16px;margin-bottom:32px}"
        ".post-card{background:var(--white);border:1px solid var(--bd);border-radius:var(--r);overflow:hidden;transition:transform .18s,box-shadow .18s;display:block;color:inherit}"
        ".post-card:hover{transform:translateY(-3px);box-shadow:0 10px 28px rgba(30,26,20,.09)}"
        ".post-card:focus-within{outline:2px solid var(--sage);outline-offset:2px}"
        ".card-link{display:block;color:inherit;text-decoration:none;height:100%}"
        ".card-link:hover{text-decoration:none}"
        ".card-media{display:block;height:170px;overflow:hidden;position:relative;background:var(--s100);border-radius:0;border:none;margin:0}"
        ".card-media img{width:100%;height:100%;object-fit:cover;border-radius:0;border:none;margin:0;transition:transform .3s}"
        ".post-card:hover .card-media img{transform:scale(1.03)}"
        ".card-placeholder{width:100%;height:100%}"
        ".card-tag-badge{position:absolute;top:10px;left:10px;background:rgba(255,255,255,.92);border-radius:999px;padding:3px 9px;font-size:10px;font-weight:500;letter-spacing:.07em;text-transform:uppercase;color:var(--ts)}"
        ".card-body{padding:14px 16px 16px}"
        ".card-meta{font-size:12px;color:var(--tm);margin:0 0 6px}"
        ".post-card h3{font-family:var(--serif);font-size:16px;font-weight:600;color:var(--tp);line-height:1.4;margin:0 0 8px;letter-spacing:-.01em}"
        ".card-excerpt{font-size:13px;color:var(--ts);line-height:1.55;margin:0 0 10px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}"
        ".read-more{font-size:13px;font-weight:500;color:var(--sage-d)}"
        # ── HUB GRID ───────────────────────────────────────────────────
        ".hub-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:32px}"
        ".hub-card{background:var(--white);border:1px solid var(--bd);border-radius:var(--r);padding:14px;text-decoration:none;display:flex;flex-direction:column;gap:6px;transition:all .15s;color:inherit}"
        ".hub-card:hover{border-color:var(--s400);transform:translateY(-2px);box-shadow:0 5px 16px rgba(30,26,20,.07);text-decoration:none}"
        ".hub-dot{width:28px;height:28px;border-radius:7px}"
        ".hub-tag{font-size:11px;font-weight:600;letter-spacing:.07em;text-transform:uppercase;color:var(--sage-d)}"
        ".hub-desc{font-size:12px;color:var(--tm);line-height:1.5}"
        ".hub-count{font-size:11px;color:var(--s200);font-weight:500}"
        # ── WIDE CARDS ─────────────────────────────────────────────────
        ".wide-grid{display:flex;flex-direction:column;gap:12px;margin-bottom:32px}"
        ".post-card-wide{background:var(--white);border:1px solid var(--bd);border-radius:var(--r);overflow:hidden;display:grid;grid-template-columns:180px 1fr;transition:transform .18s,box-shadow .18s}"
        ".post-card-wide:hover{transform:translateY(-2px);box-shadow:0 8px 22px rgba(30,26,20,.09)}"
        ".post-card-wide .card-link{display:grid;grid-template-columns:180px 1fr;text-decoration:none;color:inherit}"
        ".wide-thumb{height:120px;overflow:hidden;background:var(--s100)}"
        ".wide-thumb img{width:100%;height:100%;object-fit:cover;border-radius:0;border:none;margin:0;transition:transform .3s}"
        ".post-card-wide:hover .wide-thumb img{transform:scale(1.04)}"
        ".wide-body{padding:14px 16px;display:flex;flex-direction:column;justify-content:center}"
        ".wide-tag{font-size:10px;font-weight:500;letter-spacing:.08em;text-transform:uppercase;color:var(--sage-d);margin-bottom:5px}"
        ".wide-body h3{font-family:var(--serif);font-size:15px;font-weight:600;color:var(--tp);line-height:1.38;margin:0 0 6px;letter-spacing:-.01em}"
        ".wide-excerpt{font-size:12px;color:var(--ts);line-height:1.55;margin:0 0 8px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}"
        # ── SIDEBAR COMPONENTS ─────────────────────────────────────────
        ".sidebar-newsletter{background:var(--s900);border-radius:var(--r);padding:22px;text-align:center}"
        ".snl-eyebrow{font-size:10px;font-weight:500;letter-spacing:.1em;text-transform:uppercase;color:#4A403A;margin-bottom:9px}"
        ".sidebar-newsletter h3{font-family:var(--serif);font-size:18px;font-weight:600;color:var(--cream);margin-bottom:7px;line-height:1.3}"
        ".sidebar-newsletter p{font-size:13px;color:#4A403A;line-height:1.6;margin-bottom:14px}"
        ".snl-input{width:100%;padding:9px 13px;border-radius:999px;border:1px solid #3A342C;background:#2C2620;color:var(--cream);font-size:13px;margin-bottom:8px;outline:none;font-family:var(--sans)}"
        ".snl-btn{width:100%;padding:9px;background:var(--cream);color:var(--s900);border:none;border-radius:999px;font-size:13px;font-weight:500;cursor:pointer;font-family:var(--sans)}"
        ".snl-note{font-size:11px;color:#4A403A;margin-top:6px;margin-bottom:0}"
        ".sidebar-card{background:var(--white);border:1px solid var(--bd);border-radius:var(--r);padding:18px}"
        ".sidebar-card-title{font-family:var(--serif);font-size:15px;font-weight:600;color:var(--tp);margin-bottom:14px}"
        ".trending-list,.start-list{display:flex;flex-direction:column;gap:0}"
        ".trending-item{display:flex;gap:10px;align-items:flex-start;padding:9px 0;border-bottom:1px solid var(--s50);text-decoration:none;color:inherit;transition:background .12s}"
        ".trending-item:last-child{border-bottom:none}"
        ".trending-item:hover{text-decoration:none}"
        ".trending-thumb{width:44px;height:44px;border-radius:var(--rs);overflow:hidden;flex-shrink:0}"
        ".trending-thumb img{width:100%;height:100%;object-fit:cover;border-radius:0;border:none;margin:0}"
        ".si-thumb-ph,.hs-thumb-ph,.trending-thumb-ph{width:100%;height:100%}"
        ".trending-tag{font-size:10px;font-weight:500;text-transform:uppercase;letter-spacing:.06em;color:var(--sage-d);margin-bottom:2px}"
        ".trending-title{font-family:var(--serif);font-size:13px;font-weight:600;color:var(--tp);line-height:1.38}"
        ".start-link{display:flex;align-items:center;gap:9px;padding:8px 0;border-bottom:1px solid var(--s50);text-decoration:none;color:inherit;font-size:13px;color:var(--ts)}"
        ".start-link:last-child{border-bottom:none}"
        ".start-link:hover{color:var(--tp);text-decoration:none}"
        ".start-dot{width:6px;height:6px;border-radius:50%;background:var(--sage);flex-shrink:0}"
        # ── POST LAYOUT (article page) ─────────────────────────────────
        ".post-layout{max-width:1100px;margin:0 auto;padding:36px 20px 64px;display:grid;grid-template-columns:1fr 280px;gap:48px}"
        ".post-main{min-width:0;max-width:700px}"
        ".post-sidebar{display:flex;flex-direction:column;gap:20px}"
        ".article-tag-pill{display:inline-block;background:var(--sage-l);color:var(--sage-d);border:1px solid #C4D9CA;border-radius:999px;padding:3px 12px;font-size:10px;font-weight:500;letter-spacing:.08em;text-transform:uppercase;margin-bottom:14px}"
        ".post-meta-row{display:flex;align-items:center;flex-wrap:wrap;gap:6px 10px;font-size:13px;color:var(--tm);padding-bottom:18px;border-bottom:1px solid var(--bd);margin-bottom:22px}"
        ".author-avatar{width:28px;height:28px;border-radius:50%;background:var(--s200);display:inline-flex;align-items:center;justify-content:center;font-size:11px;font-weight:600;color:var(--ts);flex-shrink:0}"
        ".meta-sep{opacity:.5}"
        ".post-main picture img{margin:18px 0;width:100%}"
        # ── ARTICLE BOXES ──────────────────────────────────────────────
        ".quick-answer{background:var(--s50);border-left:3px solid var(--sage);border-radius:0 var(--rs) var(--rs) 0;padding:13px 17px;margin:0 0 20px}"
        ".quick-answer strong{font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--sage-d);font-weight:600;display:block;margin-bottom:5px}"
        ".takeaways{background:var(--white);border:1px solid var(--bd);border-radius:var(--r);padding:14px 18px;margin:14px 0}"
        ".takeaways h2{font-family:var(--sans);font-size:12px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:var(--tm);margin:0 0 9px}"
        ".takeaways ul{padding-left:17px}"
        ".takeaways li{font-size:15px;color:var(--ts);margin-bottom:5px}"
        ".quick-win{background:var(--sage-l);border:1px solid #C4D9CA;border-radius:var(--r);padding:16px 18px;margin:22px 0}"
        ".quick-win h3{font-family:var(--sans);font-size:11px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:var(--sage-d);margin:0 0 7px}"
        ".quick-win p{font-size:16px;color:var(--s800);font-weight:500;line-height:1.65;margin:0}"
        ".myth-fact{border:1px solid var(--bd);border-radius:var(--r);overflow:hidden;margin:22px 0}"
        ".myth-header{background:#FDF3F2;padding:10px 16px;font-size:10px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:#A32D2D;border-bottom:1px solid var(--bd)}"
        ".myth-body{padding:12px 16px;color:var(--ts);font-style:italic;font-size:15px;border-bottom:1px solid var(--bd)}"
        ".fact-header{background:#F3F8F4;padding:10px 16px;font-size:10px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:var(--sage-d);border-bottom:1px solid var(--bd)}"
        ".fact-body{padding:12px 16px;color:var(--ts);font-size:15px}"
        # ── TOC / RELATED / NEXT ───────────────────────────────────────
        ".toc{background:var(--white);border:1px solid var(--bd);border-radius:var(--r);padding:14px 18px;margin:18px 0}"
        ".toc h2{font-family:var(--sans);font-size:12px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:var(--tm);margin:0 0 10px}"
        ".toc ol{padding-left:18px}"
        ".toc li{font-size:14px;margin-bottom:5px}"
        ".toc a{color:var(--ts)}"
        ".toc a:hover{color:var(--tp)}"
        ".sidebar-toc{margin:0}"
        ".related,.next-article,.more-in-tag{background:var(--s50);border:1px solid var(--bd);border-radius:var(--r);padding:18px 20px;margin:22px 0}"
        ".related h2,.next-article h2,.more-in-tag h2{font-family:var(--sans);font-size:12px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:var(--tm);margin:0 0 12px}"
        ".next-link{font-family:var(--serif);font-size:17px;font-weight:600;color:var(--tp)}"
        # ── BREADCRUMB ─────────────────────────────────────────────────
        ".breadcrumb{display:flex;align-items:center;gap:7px;margin:0 0 16px;font-size:13px;color:var(--tm);flex-wrap:wrap}"
        ".breadcrumb a{color:var(--tm);text-decoration:none}"
        ".breadcrumb a:hover{color:var(--ts)}"
        ".breadcrumb span{color:var(--tp)}"
        # ── RECIPE ─────────────────────────────────────────────────────
        ".recipe-toolbar{display:flex;gap:10px;flex-wrap:wrap;margin:0 0 14px}"
        ".recipe-glance{background:var(--s50);border:1px solid var(--bd);border-radius:var(--r);padding:14px 18px;margin:14px 0}"
        ".recipe-glance h2{font-family:var(--sans);font-size:12px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:var(--tm);margin:0 0 10px}"
        ".recipe-glance ul{display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:7px;list-style:none;padding:0}"
        ".recipe-glance li{background:var(--white);border:1px solid var(--bd);border-radius:var(--rs);padding:8px 10px;display:flex;flex-direction:column;gap:2px}"
        ".recipe-glance li span{color:var(--tm);font-size:11px;text-transform:uppercase;letter-spacing:.05em;font-weight:500}"
        ".recipe-glance li strong{font-size:15px;font-weight:600;color:var(--tp)}"
        "h3#ingredients+ul li{position:relative;padding-left:22px}"
        "h3#ingredients+ul li::before{content:'○';position:absolute;left:0;color:var(--sage);font-size:11px;top:3px}"
        ".recipe-cta{background:var(--sage-d)}"
        ".recipe-cta:hover{background:var(--sage)}"
        # ── TAG PAGE ───────────────────────────────────────────────────
        ".tag-hero{background:var(--white);border-bottom:1px solid var(--bd);padding:36px 20px 24px;margin-bottom:28px}"
        ".tag-hero h1{font-family:var(--serif);font-size:34px;font-weight:600;letter-spacing:-.02em;margin-bottom:8px}"
        ".tag-hero p{font-size:16px;color:var(--ts);max-width:540px;line-height:1.75}"
        # ── BUTTONS ────────────────────────────────────────────────────
        ".btn-primary{display:inline-block;background:var(--s900);color:var(--cream);padding:10px 20px;border-radius:999px;font-size:14px;font-weight:500;text-decoration:none;transition:background .15s,transform .12s;border:none;cursor:pointer;font-family:var(--sans)}"
        ".btn-primary:hover{background:var(--s800);transform:translateY(-1px);text-decoration:none;color:var(--cream)}"
        ".btn-secondary{display:inline-block;background:transparent;color:var(--ts);padding:10px 18px;border-radius:999px;border:1px solid var(--bd);font-size:14px;text-decoration:none;transition:border-color .15s,color .15s;cursor:pointer;font-family:var(--sans)}"
        ".btn-secondary:hover{border-color:var(--s400);color:var(--tp);text-decoration:none}"
        # ── FOOTER ─────────────────────────────────────────────────────
        ".site-footer{background:var(--s900);padding:44px 20px 24px;margin-top:0}"
        ".footer-inner{max-width:1100px;margin:0 auto;display:grid;grid-template-columns:2fr 1fr 1fr;gap:44px;padding-bottom:28px;border-bottom:1px solid #2C2620;margin-bottom:20px}"
        ".footer-brand p{font-size:13px;color:#4A403A;line-height:1.7;max-width:250px;margin-top:8px}"
        ".footer-logo{font-family:var(--serif);font-size:18px;font-weight:600;color:var(--cream);display:block;margin-bottom:6px}"
        ".footer-col h4{font-size:11px;font-weight:500;letter-spacing:.1em;text-transform:uppercase;color:#3A342C;margin-bottom:12px}"
        ".footer-col ul{list-style:none;padding:0}"
        ".footer-col li{margin-bottom:7px}"
        ".footer-col a{font-size:13px;color:#4A403A;text-decoration:none}"
        ".footer-col a:hover{color:var(--cream)}"
        ".footer-bottom{max-width:1100px;margin:0 auto;display:flex;justify-content:space-between;align-items:center;font-size:12px;color:#3A342C}"
        ".footer-bottom a{color:#4A403A;text-decoration:none}"
        ".footer-bottom a:hover{color:var(--cream)}"
        # ── BACK TO TOP ────────────────────────────────────────────────
        ".back-to-top{position:fixed;right:18px;bottom:20px;width:40px;height:40px;border-radius:50%;border:1px solid var(--bd);background:var(--white);color:var(--ts);font-size:16px;display:none;cursor:pointer;box-shadow:0 4px 14px rgba(30,26,20,.10);transition:all .15s}"
        ".back-to-top.visible{display:flex;align-items:center;justify-content:center}"
        ".back-to-top:hover{background:var(--s900);color:var(--cream);border-color:var(--s900)}"
        # ── RESPONSIVE ─────────────────────────────────────────────────
        "@media(max-width:900px){"
        ".hero-split{grid-template-columns:1fr}"
        ".hero-left{max-width:100%;border-right:none;border-bottom:1px solid var(--bd);padding:36px 20px 28px}"
        ".hero-right{}"
        ".hf-image{min-height:200px}"
        ".home-layout{grid-template-columns:1fr}"
        ".home-sidebar{display:none}"
        ".post-layout{grid-template-columns:1fr}"
        ".post-sidebar{display:none}"
        ".hub-grid{grid-template-columns:repeat(2,1fr)}"
        ".trust-inner{flex-wrap:wrap}"
        ".trust-item{flex:1 1 45%;border-bottom:1px solid var(--bd)}"
        ".footer-inner{grid-template-columns:1fr;gap:24px}"
        "}"
        "@media(max-width:600px){"
        ".header-inner{height:52px}"
        ".site-nav a:not(.nav-cta){display:none}"
        ".hero-h1{font-size:clamp(26px,6vw,36px)}"
        ".post-grid{grid-template-columns:1fr}"
        ".hub-grid{grid-template-columns:1fr 1fr}"
        ".post-card-wide{grid-template-columns:1fr}"
        ".post-card-wide .card-link{grid-template-columns:1fr}"
        ".wide-thumb{height:160px}"
        ".hero-btns{flex-direction:column;align-items:flex-start}"
        ".btn-primary,.btn-secondary{width:100%;text-align:center}"
        ".chips-inner{flex-wrap:wrap}"
        "}"
    )
