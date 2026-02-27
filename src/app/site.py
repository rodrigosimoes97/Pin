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
    same_tag_more = _pick_more_in_tag(posts, tag, post.get("slug", ""), 2)
    next_post = _pick_next_post(posts, tag, post.get("slug", ""))
    article_html, toc_items = _inject_h2_ids_and_collect_toc(_normalize_article_headings(post["html"]))
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


def _pick_next_post(posts: list[dict[str, str]], tag: str, current_slug: str) -> dict[str, str] | None:
    same_tag = [post for post in posts if post.get("slug") != current_slug and post.get("tag") == tag]
    if same_tag:
        return same_tag[0]
    fallback = [post for post in posts if post.get("slug") != current_slug]
    return fallback[0] if fallback else None


def _pick_more_in_tag(posts: list[dict[str, str]], tag: str, current_slug: str, limit: int) -> list[dict[str, str]]:
    return [post for post in posts if post.get("slug") != current_slug and post.get("tag") == tag][:limit]


def _append_related_posts_cards(html: str, related: list[dict[str, str]]) -> str:
    if not related:
        return html
    cards = "".join(_render_post_card(item, Path("."), "") for item in related)
    return f"{html}\n<section class='related'><h2>Related posts</h2><div class='post-grid'>{cards}</div></section>"


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
    article_html = re.sub(r"<h1(\\b[^>]*)>", r"<h2\1>", article_html, flags=re.IGNORECASE)
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
    published_date = _iso_date_or_fallback(post.get("datePublished") or post.get("date"), run_date.isoformat())
    modified_date = _iso_date_or_fallback(post.get("dateModified") or post.get("date_modified"), published_date)
    is_recipe = str(tag) == "recipes"
    recipe_data = post.get("recipe") if is_recipe and isinstance(post.get("recipe"), dict) else None

    toc_block = ""
    if len(toc_items) >= 2:
        toc_links = "".join(
            f"<li><a href='#{escape(h2_id)}'>{escape(title)}</a></li>" for title, h2_id in toc_items[:6]
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
    recipe_jsonld = ""
    recipe_summary = ""
    recipe_toolbar = ""
    more_in_tag_block = ""
    if recipe_data:
        recipe_jsonld = f"<script type='application/ld+json'>{json.dumps(_build_recipe_schema(post, recipe_data, canonical, og_image, run_date))}</script>"
        recipe_summary = _render_recipe_summary(recipe_data)
        recipe_toolbar = (
            "<div class='recipe-toolbar'>"
            "<a class='btn-primary recipe-cta' href='#recipe'>Jump to recipe</a>"
            "<button type='button' class='btn-secondary print-recipe' onclick='window.print()'>Print recipe</button>"
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
        related_block = f"<section class='related'><h2>Related posts</h2><div class='post-grid'>{related_cards}</div></section>"

    same_tag_cards = "".join(_render_post_card(item, Path("."), "") for item in same_tag_more)
    same_tag_cta = (
        f"<a class='btn-secondary' href='tag/{escape(tag)}.html'>Visit {escape(str(tag))} hub</a>"
        if tag
        else ""
    )
    if same_tag_cards:
        more_in_tag_block = (
            "<section class='related more-in-tag'>"
            f"<h2>More in {escape(str(tag))}</h2>"
            f"<div class='topic-row-actions'>{same_tag_cta}</div>"
            f"<div class='post-grid'>{same_tag_cards}</div>"
            "</section>"
        )

    recipe_back_to_top = "<p class='micro-link'><a href='#top'>Back to top ↑</a></p>" if recipe_data else ""

    takeaway_items = "".join(f"<li>{escape(item)}</li>" for item in key_takeaways)

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
{recipe_jsonld}
</head>

<body>
<a id='top'></a>
<main class='container'>
<header class='header'><a href='index.html'>{escape(site_title)}</a></header>
<article>
<nav class='top-nav'><a href='index.html'>Home</a><span>·</span><a href='tag/{escape(tag)}.html'>{escape(tag)} hub</a></nav>
<h1>{escape(post['title'])}</h1>
{recipe_toolbar}
{recipe_summary}
<div class='quick-answer'><strong>Quick answer:</strong> {escape(quick_answer)}</div>
<div class='takeaways'><h2>Key takeaways</h2><ul>{takeaway_items}</ul></div>
<p class='meta'>{published_date} · {reading_time} min read · <a class='tag-pill' href='tag/{escape(tag)}.html'>{escape(tag)}</a>{f" · Updated: {modified_date}" if modified_date != published_date else ""}</p>
<img src='{escape(hero_path_rel)}' alt='{escape(post['alt_text'])}' fetchpriority='high' loading='eager'>
{toc_block}
{article_html}
{recipe_back_to_top}
{next_block}
{more_in_tag_block}
{related_block}
</article>
<footer class='site-footer'>
<div class='footer-links'><a href='index.html'>Home</a><a href='tag/{escape(tag)}.html'>Tags</a><a href='about.html'>About</a><a href='sitemap.xml'>Sitemap</a><a href='#top'>Back to top</a></div>
<p>Educational only — not medical advice.</p>
</footer>
</main>
<button type='button' class='back-to-top' aria-label='Back to top'>↑</button>
<script>{_back_to_top_js()}</script>
</body>
</html>"""


def _tag_intro(tag: str) -> str:
    readable = tag.replace("-", " ")
    return f"Explore practical {readable} guides, checklists, and step-by-step posts for daily use."


def _write_index(docs_dir: Path, base_url: str, site_title: str, posts: list[dict[str, str]]) -> None:
    public_base = _effective_base_url(base_url)
    top_tags = [tag for tag, _ in Counter((p.get("tag") or "health") for p in posts).most_common(10)]
    chips = "".join(f"<a class='tag-pill' href='tag/{escape(tag)}.html'>{escape(tag)}</a>" for tag in top_tags)
    filter_chips = "".join(
        f"<button type='button' class='filter-chip' data-filter-tag='{escape(tag)}'>{escape(tag)}</button>" for tag in top_tags
    )
    latest_url = escape(posts[0]["url"]) if posts else "#posts"
    latest_cards = "".join(_render_post_card(post, docs_dir, "") for post in posts[:12])
    start_here_cards = "".join(_render_post_card(post, docs_dir, "") for post in _start_here_posts(posts, 6))
    continue_cards = "".join(_render_post_card(post, docs_dir, "") for post in _continue_reading_posts(posts, 3))
    html = f"""<!doctype html>
<html lang='en'>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width, initial-scale=1'>
<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-QHJBWL5WXE"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());

  gtag('config', 'G-QHJBWL5WXE');
</script>
<title>Practical Habits to Feel Better Daily</title>
<meta name='description' content='Practical US health content for sleep, gut health, workouts, and habits.'>
<meta name='robots' content='index,follow'>
<link rel='canonical' href='{public_base}/'>
<style>{_base_css()}</style>
</head>
<body>
<header class='site-header'>
<div class='container header-inner'>
<div>
<a class='site-title' href='index.html'>{escape(site_title)}</a>
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
<h1>{escape(site_title)}: practical habits that help you feel better, daily</h1>
<p class='hero-intro'>Evidence-informed, practical health guides for US readers on sleep, longevity, gut health, stress, and simple recipes.</p>
<p class='trust-line'>Updated regularly • Evidence-informed • Educational only</p>
<div class='hero-actions'>
<a class='btn-primary' href='#start-here'>Start here</a>
<a class='btn-secondary' href='{latest_url}'>Read the latest</a>
</div>
</section>

<section id='start-here'>
<h2 class='section-title'>Start here</h2>
<div class='post-grid'>{start_here_cards}</div>
</section>

<section id='search'>
<h2 class='section-title'>Find what you need</h2>
<input id='search-input' class='search-input' type='search' placeholder='Search by title, excerpt, or topic'>
<div class='tag-row'><button type='button' class='filter-chip active' data-filter-tag='all'>All</button>{filter_chips}</div>
</section>

<section id='posts'>
<h2 class='section-title'>Latest</h2>
<div class='post-grid' id='post-grid'>{latest_cards}</div>
</section>

<section id='continue'>
<h2 class='section-title'>Continue reading</h2>
<div class='post-grid'>{continue_cards}</div>
</section>

<section id='tags'>
<h2 class='section-title'>Browse by topic</h2>
<div class='tag-row'>{chips}</div>
</section>
</main>
<footer class='site-footer'>
<div class='container'>
<div class='footer-links'><a href='index.html'>Home</a><a href='about.html'>About</a><a href='sitemap.xml'>Sitemap</a><a href='#top'>Top</a></div>
<p>Educational only — not medical advice.</p>
<p>© {date.today().year} {escape(site_title)}</p>
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
    cards.forEach((card) => {{
      const text = [card.dataset.title, card.dataset.excerpt, card.dataset.tag].join(' ').toLowerCase();
      const tagOk = selectedTag === 'all' || (card.dataset.tag || '') === selectedTag;
      const queryOk = !q || text.includes(q);
      card.style.display = (tagOk && queryOk) ? '' : 'none';
    }});
  }};
  input?.addEventListener('input', apply);
  chips.forEach((chip) => chip.addEventListener('click', () => {{
    selectedTag = chip.dataset.filterTag || 'all';
    chips.forEach((c) => c.classList.toggle('active', c === chip));
    apply();
  }}));
}})();
</script>
</body>
</html>"""
    (docs_dir / "index.html").write_text(html, encoding="utf-8")


def _render_post_card(post: dict[str, str], docs_dir: Path, link_prefix: str) -> str:
    hero = (post.get("hero") or "").strip()
    title = escape(post["title"])
    tag = escape(post.get("tag", "health"))
    excerpt = escape(_post_excerpt(post, docs_dir))
    reading = _reading_time_minutes_for_post(post, docs_dir)
    link = f"{link_prefix}{escape(post['url'])}"
    tag_link = f"{link_prefix}tag/{tag}.html"
    media = (
        f"<img src='{escape(hero)}' alt='{title}' loading='lazy'>"
        if hero
        else "<div class='placeholder' aria-hidden='true'>✦</div>"
    )
    return (
        f"<article class='post-card' data-title='{title}' data-excerpt='{excerpt}' data-tag='{tag}'>"
        f"<a class='card-link' href='{link}'>"
        f"<span class='card-media'>{media}</span>"
        f"<h3>{title}</h3>"
        f"<p class='meta'>{escape(post['date'])} · "
        f"{reading} min read · <span class='tag-pill'>{tag}</span></p>"
        f"<p class='excerpt'>{excerpt}</p>"
        "<span class='read-more'>Read more →</span>"
        "</a>"
        f"<p><a class='card-tag-link' href='{tag_link}'>Explore {tag}</a></p>"
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


def _reading_time_minutes_from_html(html: str) -> int:
    text = re.sub(r"<[^>]+>", " ", html)
    words = len(re.findall(r"\b\w+\b", text))
    return max(1, round(words / 200))


def _reading_time_minutes_for_post(post: dict[str, str], docs_dir: Path) -> int:
    html_value = (post.get("html") or "").strip()
    if html_value:
        return _reading_time_minutes_from_html(html_value)
    target = docs_dir / post.get("url", "")
    if target.exists():
        return _reading_time_minutes_from_html(target.read_text(encoding="utf-8"))
    return 1


def _start_here_posts(posts: list[dict[str, str]], limit: int) -> list[dict[str, str]]:
    per_tag: dict[str, dict[str, str]] = {}
    for post in posts:
        tag = post.get("tag", "health")
        if tag not in per_tag:
            per_tag[tag] = post
    return list(per_tag.values())[:limit]


def _continue_reading_posts(posts: list[dict[str, str]], limit: int) -> list[dict[str, str]]:
    picks: list[dict[str, str]] = []
    seen_tags: set[str] = set()
    for post in posts:
        tag = post.get("tag", "health")
        if tag in seen_tags:
            continue
        picks.append(post)
        seen_tags.add(tag)
        if len(picks) >= limit:
            break
    if len(picks) < limit:
        for post in posts:
            if post in picks:
                continue
            picks.append(post)
            if len(picks) >= limit:
                break
    return picks[:limit]


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
    if len(bullets) < 3:
        first_para = re.search(r"<p[^>]*>(.*?)</p>", article_html, flags=re.IGNORECASE | re.DOTALL)
        if first_para:
            clean_para = re.sub(r"<[^>]+>", "", first_para.group(1)).strip()
            if clean_para:
                bullets.append(clean_para[:160].rstrip(" .,;:") + ".")
    defaults = [
        "Use simple, consistent actions you can repeat this week.",
        "Prioritize evidence-informed habits over one-off hacks.",
        "Track what feels sustainable and adjust gradually.",
    ]
    while len(bullets) < 3:
        bullets.append(defaults[len(bullets)])
    return bullets[:3]


def _render_recipe_summary(recipe: dict[str, object]) -> str:
    rows = [
        ("Prep", f"{recipe.get('prep_time_minutes', '')} min"),
        ("Cook", f"{recipe.get('cook_time_minutes', '')} min"),
        ("Total", f"{recipe.get('total_time_minutes', '')} min"),
        ("Servings", str(recipe.get('servings', ''))),
    ]
    calories = str(recipe.get("calories_per_serving", "")).strip()
    if calories:
        rows.append(("Calories", calories))
    items = "".join(f"<li><span>{escape(label)}</span><strong>{escape(value)}</strong></li>" for label, value in rows if value)
    return f"<section class='recipe-glance'><h2>Recipe at a glance</h2><ul>{items}</ul></section>"


def _duration(minutes: object) -> str:
    try:
        value = max(1, int(minutes))
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
    ingredients = [str(item).strip() for item in recipe.get("ingredients", []) if str(item).strip()]
    instructions = [str(item).strip() for item in recipe.get("instructions", []) if str(item).strip()]
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
        "recipeInstructions": [{"@type": "HowToStep", "text": item} for item in instructions],
    }
    calories = str(recipe.get("calories_per_serving", "")).strip()
    if calories:
        data["nutrition"] = {"@type": "NutritionInformation", "calories": calories}
    return data


def _back_to_top_js() -> str:
    return """(() => {
  const button = document.querySelector('.back-to-top');
  if (!button) return;
  const refresh = () => {
    button.classList.toggle('visible', window.scrollY > 400);
  };
  button.addEventListener('click', () => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });
  window.addEventListener('scroll', refresh, { passive: true });
  refresh();
})();"""


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
<header class='site-header'>
<div class='container header-inner'>
<div>
<a class='site-title' href='index.html'>{escape(site_title)}</a>
<p class='site-subtitle'>US-focused health tips, habits, and recipes</p>
</div>
<nav class='site-nav'>
<a href='index.html'>Home</a>
<a class='active' href='about.html'>About</a>
</nav>
</div>
</header>
<main class='container'>
<section class='hero'>
<h1>About</h1>
<p>This site publishes practical, US-focused health content designed to be clear, useful, and easy to apply in daily life.</p>
<h2>Editorial note</h2>
<p>Content is for informational purposes only and is not medical advice, diagnosis, or treatment. Always consult a qualified healthcare professional for personal medical guidance.</p>
<p><a href='sitemap.xml'>View sitemap.xml</a></p>
</section>
</main>
<footer class='site-footer'>
<div class='container'>
<div class='footer-links'><a href='index.html'>Home</a><a href='about.html'>About</a><a href='sitemap.xml'>Sitemap</a></div>
<p>Educational only — not medical advice.</p>
</div>
</footer>
<button type='button' class='back-to-top' aria-label='Back to top'>↑</button>
<script>{_back_to_top_js()}</script>
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
        unique_posts = sorted(group[:], key=lambda item: item.get("date", ""), reverse=True)
        start_here = unique_posts[:4]
        latest = unique_posts[4:]
        tag_pills = "".join(
            f"<a class='tag-pill' href='{escape(other)}.html'>{escape(other)}</a>"
            for other in grouped.keys()
            if other != tag
        )
        start_cards = "".join(_render_post_card(item, docs_dir, "../") for item in start_here)
        latest_cards = "".join(_render_post_card(item, docs_dir, "../") for item in latest)

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
<section class='hero tag-hero'>
<p><a href='../index.html'>← Back to home</a></p>
<h1>{escape(tag.title())} hub</h1>
<p>{escape(_tag_intro(tag))}</p>
<p class='trust-line'>Your topic hub for practical steps and latest posts.</p>
</section>
<h2>Start here in {escape(tag)}</h2>
<div class='post-grid'>{start_cards}</div>
<h2>Latest in {escape(tag)}</h2>
<div class='post-grid'>{latest_cards}</div>
<h2>Explore other topics</h2>
<div class='tag-row'>{tag_pills}</div>
</main>
<button type='button' class='back-to-top' aria-label='Back to top'>↑</button>
<script>{_back_to_top_js()}</script>
</body>
</html>"""
        (tag_dir / file_name).write_text(page, encoding="utf-8")

    return urls


def _write_sitemap(docs_dir: Path, base_url: str, posts: list[dict[str, str]], tag_pages: list[str]) -> None:
    public_base = _effective_base_url(base_url)
    known_dates = [str(post.get("date", "")).strip() for post in posts[:200] if re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(post.get("date", "")).strip())]
    default_lastmod = max(known_dates, default=date.today().isoformat())
    post_lastmods = {
        post.get("url", ""): _iso_date_or_fallback(post.get("date"), default_lastmod)
        for post in posts[:200]
        if post.get("url")
    }
    newest_post_lastmod = max(post_lastmods.values(), default=default_lastmod)
    tag_lastmods: dict[str, str] = {}
    for post in posts[:200]:
        tag = post.get("tag", "health")
        lastmod = _iso_date_or_fallback(post.get("date"), default_lastmod)
        tag_lastmods[tag] = max(tag_lastmods.get(tag, "0000-00-00"), lastmod)

    rows = [
        "  <url>",
        f"    <loc>{public_base}/</loc>",
        f"    <lastmod>{newest_post_lastmod}</lastmod>",
        "  </url>",
        "  <url>",
        f"    <loc>{public_base}/about.html</loc>",
        f"    <lastmod>{newest_post_lastmod}</lastmod>",
        "  </url>",
    ]
    for post in posts[:200]:
        rows.extend(
            [
                "  <url>",
                f"    <loc>{public_base}/{escape(post['url'])}</loc>",
                f"    <lastmod>{escape(post_lastmods.get(post.get('url', ''), default_lastmod))}</lastmod>",
                "  </url>",
            ]
        )
    for tag_page in sorted(set(tag_pages)):
        tag_name = Path(tag_page).stem
        rows.extend(
            [
                "  <url>",
                f"    <loc>{public_base}/{escape(tag_page)}</loc>",
                f"    <lastmod>{tag_lastmods.get(tag_name, newest_post_lastmod)}</lastmod>",
                "  </url>",
            ]
        )
    xml = "\n".join(
       [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
            *rows,
            '</urlset>',
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
        "body{margin:0;background:radial-gradient(circle at top,#111a2b 0,#070b12 45%,#05080f 100%);color:#eaf1fb;"
        "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;"
        "line-height:1.75;}"
        ".container{max-width:1100px;margin:0 auto;padding:22px 16px 68px;}"
        ".site-header{position:sticky;top:0;z-index:20;background:rgba(7,11,18,.92);backdrop-filter:blur(8px);border-bottom:1px solid #1b2533;}"
        ".header-inner{padding-top:10px;padding-bottom:10px;display:flex;justify-content:space-between;gap:18px;align-items:center;}"
        ".site-title{font-size:18px;font-weight:700;color:#f8fbff;}"
        ".site-subtitle{margin:2px 0 0;color:#a9bad0;font-size:13px;line-height:1.45;}"
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
        ".trust-line{color:#9fb0c3;font-size:14px;margin:8px 0 0;}"
        ".hero-actions{display:flex;gap:10px;flex-wrap:wrap;margin-top:10px;}"
        ".btn-primary{display:inline-block;margin-top:8px;background:#1d4ed8;border:1px solid #3765e6;color:#f8fbff;padding:9px 14px;border-radius:10px;font-weight:600;transition:transform .16s ease,background .16s ease;}"
        ".btn-primary:hover{text-decoration:none;background:#2a5ce8;transform:translateY(-1px);}"
        ".btn-secondary{display:inline-block;margin-top:8px;background:#101a29;border:1px solid #355176;color:#dce9f9;padding:9px 14px;border-radius:10px;font-weight:600;}"
        ".search-input{width:min(560px,100%);padding:10px 12px;border-radius:10px;background:#0c1624;border:1px solid #2a3d53;color:#e6edf6;}"
        ".filter-chip{background:#101a29;border:1px solid #355176;color:#cfe3fb;padding:6px 10px;border-radius:999px;cursor:pointer;}"
        ".filter-chip.active{background:#1d4ed8;border-color:#4a78ff;}"
        ".section-title{margin:18px 0 12px;}"
        ".post-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px;}"
        ".post-card{background:#0b1320;border:1px solid #223247;border-radius:14px;padding:12px;box-shadow:0 10px 24px rgba(0,0,0,.22);transition:transform .16s ease,border-color .16s ease,box-shadow .16s ease;}"
        ".post-card:hover{transform:translateY(-3px);border-color:#4a78a8;box-shadow:0 18px 32px rgba(0,0,0,.34);}"
        ".card-link{display:block;color:inherit;}"
        ".card-link:hover{text-decoration:none;}"
        ".card-media{display:block;border-radius:12px;overflow:hidden;border:1px solid #1f2a3a;height:170px;background:#0f1a2a;margin-bottom:10px;}"
        ".card-media img{width:100%;height:100%;object-fit:cover;margin:0;border:none;border-radius:0;}"
        ".card-media .placeholder{width:100%;height:100%;background:linear-gradient(135deg,#0e1b2f,#17263d);display:grid;place-items:center;font-size:24px;color:#9bc8f7;}"
        ".post-card h3{margin:6px 0 6px;font-size:19px;line-height:1.35;}"
        ".post-card .meta{margin:0 0 8px;}"
        ".excerpt{margin:0 0 8px;color:#c5d2e3;font-size:15px;line-height:1.55;}"
        ".read-more{font-size:14px;font-weight:600;color:#9ad8ff;}"
        ".card-tag-link{font-size:13px;color:#9ad8ff;}"
        ".post-card:focus-within{outline:2px solid #7dd3fc;outline-offset:2px;}"
        "h1{font-size:clamp(26px,4.2vw,40px);line-height:1.15;margin:10px 0 12px;letter-spacing:-0.02em;}"
        "h2{margin-top:30px;font-size:24px;line-height:1.24;letter-spacing:-.01em;}"
        "h3{margin-top:20px;font-size:20px;}"
        "p,li{font-size:18px;}"
        "img{max-width:100%;height:auto;border-radius:14px;display:block;margin:14px 0;border:1px solid #1f2a3a;}"
        "a{color:#7dd3fc;text-decoration:none;}a:hover{text-decoration:underline;}"
        ".meta{color:#9fb0c3;font-size:14px;margin:8px 0 14px;}"
        ".quick-answer{background:#0c1624;border:1px solid #223247;border-radius:12px;padding:10px 12px;}"
        ".takeaways{background:#101a29;border:1px solid #2a3d53;border-radius:12px;padding:10px 14px;margin:12px 0;}"
        ".takeaways h2{font-size:18px;margin:2px 0 8px;}"
        ".tag-row{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0 18px;}"
        ".tag-pill{display:inline-block;background:rgba(125,211,252,.16);"
        "border:1px solid rgba(125,211,252,.32);color:#e8eef5;border-radius:999px;"
        "padding:3px 10px;font-size:12px;}"
        ".toc,.related,.next-article{background:#101a29;border:1px solid #26374b;border-radius:14px;"
        "padding:12px 14px;margin:16px 0;}"
        ".next-link{font-size:18px;font-weight:700;}"
        ".site-footer{border-top:1px solid #223247;background:#08101a;padding:18px 0;margin-top:30px;}"
        ".footer-links{display:flex;flex-wrap:wrap;gap:12px;font-size:14px;}"
        "ul,ol{padding-left:22px;}"
        "small{color:#9fb0c3;}"
        ".recipe-toolbar{display:flex;gap:10px;flex-wrap:wrap;margin:8px 0 14px;}"        ".recipe-glance{background:#0f1a2a;border:1px solid #2a3d53;border-radius:14px;padding:10px 14px;margin:12px 0 18px;}"        ".recipe-glance h2{font-size:18px;margin:0 0 8px;}"        ".recipe-glance ul{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:8px;list-style:none;padding:0;margin:0;}"        ".recipe-glance li{background:#0b1320;border:1px solid #1d2d44;border-radius:10px;padding:8px 10px;display:flex;flex-direction:column;gap:2px;font-size:14px;}"        ".recipe-glance li span{color:#9fb0c3;font-size:12px;text-transform:uppercase;letter-spacing:.06em;}"        "h3#ingredients + ul li{list-style:none;position:relative;padding-left:28px;margin:8px 0;}"        "h3#ingredients + ul li::before{content:'☐';position:absolute;left:0;top:0;color:#9ad8ff;}"        "h3#instructions + ol li{margin:10px 0;padding-left:2px;}"        ".micro-link{margin-top:12px;font-size:14px;}"        ".topic-row-actions{display:flex;justify-content:flex-end;margin:-4px 0 10px;}"        ".back-to-top{position:fixed;right:16px;bottom:18px;width:42px;height:42px;border-radius:999px;border:1px solid #3b5472;background:#0f1a2a;color:#dbeafe;font-size:18px;display:none;cursor:pointer;box-shadow:0 10px 24px rgba(0,0,0,.3);}"        ".back-to-top.visible{display:block;}"        "@media (max-width:760px){.site-header{position:static;}.header-inner{display:block;}.site-nav{margin-top:8px;gap:10px;}.site-subtitle{font-size:12px;}.container{padding-top:14px;}}"
    )
