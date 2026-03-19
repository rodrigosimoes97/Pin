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
    assets_dir = docs_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    
    # Fix 1: CSS externo para cache
    (assets_dir / "style.css").write_text(_base_css(), encoding="utf-8")
    
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

    # Fix 10: Preload da imagem hero
    preload_hero = f"<link rel='preload' as='image' href='{hero_path_rel}' fetchpriority='high'>"

    # Fix 7: Breadcrumb Visual
    breadcrumb_html = f"""
    <nav aria-label='breadcrumb' class='breadcrumb'>
      <a href='index.html'>Home</a> › 
      <a href='tag/{tag}.html'>{escape(str(tag)).replace("-", " ")}</a> › 
      <span>{escape(str(post['title']))}</span>
    </nav>
    """

    toc_block = ""
    if len(toc_items) >= 2:
        toc_links = "".join(f"<li><a href='#{escape(h2_id)}'>{escape(title)}</a></li>" for title, h2_id in toc_items[:6])
        toc_block = f"<nav class='toc'><h2>Table of contents</h2><ol>{toc_links}</ol></nav>"

    quick_answer = _build_quick_answer(article_html)
    reading_time = _reading_time_minutes_from_html(article_html)
    key_takeaways = _build_key_takeaways(article_html, quick_answer)

    # Schemas (Fix 8: Autor sinalizado)
    article_schema = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": post["title"],
        "description": description,
        "datePublished": published_date,
        "dateModified": modified_date,
        "author": {"@type": "Person", "name": "RodrigoS", "url": f"{public_base}/about.html"},
        "mainEntityOfPage": canonical,
        "image": og_image,
        "about": tag,
    }

    faq_items_raw = post.get("faq")
    faq_items = faq_items_raw if isinstance(faq_items_raw, list) else _extract_faq_items(article_html)
    faq_schema = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [{"@type": "Question", "name": item["question"], "acceptedAnswer": {"@type": "Answer", "text": item["answer"]}} for item in faq_items],
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
    if recipe_data:
        recipe_jsonld = f"<script type='application/ld+json'>{json.dumps(_build_recipe_schema(post, recipe_data, canonical, og_image, run_date))}</script>"
        recipe_summary = _render_recipe_summary(recipe_data)
        recipe_toolbar = "<div class='recipe-toolbar'><a class='btn-primary recipe-cta' href='#recipe'>Jump to recipe</a></div>"

    next_block = ""
    if next_post:
        next_block = f"<section class='next-article'><h2>Next article</h2><a class='next-link' href='{escape(next_post['url'])}'>{escape(next_post['title'])} →</a></section>"

    related_block = ""
    if related:
        related_cards = "".join(_render_post_card(item, Path("."), "") for item in related)
        related_block = f"<section class='related'><h2>Related posts</h2><div class='post-grid'>{related_cards}</div></section>"

    takeaway_items = "".join(f"<li>{escape(item)}</li>" for item in key_takeaways)

    # Fix 9: Picture fallback para WebP
    hero_webp = hero_path_rel.replace(".jpg", ".webp").replace(".png", ".webp")
    hero_picture = f"""
    <picture>
      <source srcset='{hero_webp}' type='image/webp'>
      <img src='{hero_path_rel}' alt='{escape(post['alt_text'])}' width='1200' height='630' fetchpriority='high' loading='eager'>
    </picture>
    """

    return f"""<!doctype html>
<html lang='en' dir='ltr'>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width, initial-scale=1'>
<title>{escape(post['title'])}</title>
<meta name='description' content='{escape(description)}'>
<meta name='author' content='RodrigoS'>
<meta name='robots' content='index,follow'>
<link rel='canonical' href='{canonical}'>
<link rel='alternate' hreflang='en' href='{canonical}'>
{preload_hero}
<link rel='stylesheet' href='assets/style.css'>
<meta property='og:type' content='article'>
<meta property='og:title' content='{escape(post['title'])}'>
<meta property='og:description' content='{escape(description)}'>
<meta property='og:url' content='{canonical}'>
<meta property='og:image' content='{og_image}'>
<meta name='twitter:card' content='summary_large_image'>
<meta name='twitter:title' content='{escape(post['title'])}'>
<meta name='twitter:description' content='{escape(description)}'>
<meta name='twitter:image' content='{og_image}'>
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
{breadcrumb_html}
<h1>{escape(post['title'])}</h1>
{recipe_toolbar}
{recipe_summary}
<div class='quick-answer'><strong>Quick answer:</strong> {escape(quick_answer)}</div>
<div class='takeaways'><h2>Key takeaways</h2><ul>{takeaway_items}</ul></div>
<p class='meta'>{published_date} · {reading_time} min read · <a class='tag-pill' href='tag/{escape(tag)}.html'>{escape(tag)}</a></p>
{hero_picture}
{toc_block}
{article_html}
{next_block}
{related_block}
</article>
<footer class='site-footer'>
<div class='footer-links'><a href='index.html'>Home</a><a href='about.html'>About</a><a href='sitemap.xml'>Sitemap</a></div>
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
    latest_cards = "".join(_render_post_card(post, docs_dir, "") for post in posts[:12])
    
    html = f"""<!doctype html>
<html lang='en'>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width, initial-scale=1'>
<link rel="preconnect" href="https://images.pexels.com">
<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "Organization",
  "name": "{escape(site_title)}",
  "url": "{public_base}",
  "logo": "{public_base}/assets/logo.png",
  "sameAs": ["https://www.pinterest.com/your-profile"]
}}
</script>
<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "WebSite",
  "name": "Practical Habits",
  "url": "{public_base}/",
  "potentialAction": {{
    "@type": "SearchAction",
    "target": "{public_base}/index.html?q={{search_term_string}}",
    "query-input": "required name=search_term_string"
  }}
}}
</script>
<title>Practical Habits to Feel Better Daily</title>
<meta name='description' content='Practical US health content for sleep, gut health, workouts, and habits.'>
<link rel='canonical' href='{public_base}/'>
<link rel='stylesheet' href='assets/style.css'>
</head>
<body>
<header class='site-header'>
<div class='container header-inner'>
<div><a class='site-title' href='index.html'>{escape(site_title)}</a></div>
<nav class='site-nav'><a href='index.html'>Home</a><a href='about.html'>About</a></nav>
</div>
</header>
<main class='container'>
<section class='hero'>
<h1>Practical habits that help you feel better, daily</h1>
<p class='hero-intro'>Evidence-informed health guides for US readers on sleep, longevity, and gut health.</p>
</section>
<section id='posts'>
<h2 class='section-title'>Latest Articles</h2>
<div class='post-grid' id='post-grid'>{latest_cards}</div>
</section>
</main>
<footer class='site-footer'>
<div class='container'><div class='footer-links'><a href='index.html'>Home</a><a href='about.html'>About</a><a href='sitemap.xml'>Sitemap</a></div></div>
</footer>
</body>
</html>"""
    (docs_dir / "index.html").write_text(html, encoding="utf-8")

def _render_post_card(post: dict[str, str], docs_dir: Path, link_prefix: str) -> str:
    hero = (post.get("hero") or "").strip()
    title = escape(post["title"])
    tag = escape(post.get("tag", "health"))
    link = f"{link_prefix}{escape(post['url'])}"
    media = f"<img src='{escape(hero)}' alt='{title}' width='400' height='225' loading='lazy'>" if hero else ""
    return f"""<article class='post-card'>
<a class='card-link' href='{link}'>
<span class='card-media'>{media}</span>
<h3>{title}</h3>
<p class='meta'>{escape(post['date'])} · <span class='tag-pill'>{tag}</span></p>
</a></article>"""

def _reading_time_minutes_from_html(html: str) -> int:
    text = re.sub(r"<[^>]+>", " ", html)
    words = len(re.findall(r"\b\w+\b", text))
    return max(1, round(words / 200))

def _build_key_takeaways(article_html: str, quick_answer: str) -> list[str]:
    return ["Consistent daily action.", "Evidence-informed choices.", "Sustainable progress."]

def _render_recipe_summary(recipe: dict[str, object]) -> str:
    return f"<section class='recipe-glance'>Prep: {recipe.get('prep_time_minutes')}m | Cook: {recipe.get('cook_time_minutes')}m</section>"

def _duration(minutes: object) -> str:
    return f"PT{minutes}M"

def _build_recipe_schema(post, recipe, canonical, og_image, run_date) -> dict:
    return {"@type": "Recipe", "name": post["title"]}

def _back_to_top_js() -> str:
    return "/* JS minimal */"

def _write_about_page(docs_dir: Path, base_url: str, site_title: str) -> None:
    (docs_dir / "about.html").write_text("About page content", encoding="utf-8")

def _write_tag_pages(docs_dir: Path, base_url: str, site_title: str, posts: list[dict[str, str]]) -> list[str]:
    # Fix 3: Meta description da tag page usando _tag_intro
    tag_dir = docs_dir / "tag"
    tag_dir.mkdir(parents=True, exist_ok=True)
    tags = set(p.get("tag", "health") for p in posts)
    urls = []
    for tag in tags:
        intro = _tag_intro(tag)
        content = f"<html><head><title>{tag}</title><meta name='description' content='{escape(intro)}'><link rel='stylesheet' href='../assets/style.css'></head><body><h1>{tag}</h1></body></html>"
        (tag_dir / f"{tag}.html").write_text(content, encoding="utf-8")
        urls.append(f"tag/{tag}.html")
    return urls

def _write_sitemap(docs_dir: Path, base_url: str, posts: list[dict[str, str]], tag_pages: list[str]) -> None:
    public_base = _effective_base_url(base_url)
    rows = [f"<url><loc>{public_base}/</loc><priority>1.0</priority></url>"]
    for post in posts[:200]:
        rows.append(f"<url><loc>{public_base}/{post['url']}</loc><lastmod>{post['date']}</lastmod></url>")
    xml = '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + "".join(rows) + "</urlset>"
    (docs_dir / "sitemap.xml").write_text(xml, encoding="utf-8")

def _write_robots(docs_dir: Path, base_url: str) -> None:
    public_base = _effective_base_url(base_url)
    (docs_dir / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {public_base}/sitemap.xml", encoding="utf-8")

def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")

def _base_css() -> str:
    return """
body{margin:0;background:#05080f;color:#eaf1fb;font-family:system-ui,-apple-system,sans-serif;line-height:1.8;}
.container{max-width:1100px;margin:0 auto;padding:20px;}
article{max-width:720px;margin:0 auto;}
.site-header{position:sticky;top:0;z-index:100;background:rgba(5,8,15,0.8);backdrop-filter:blur(10px);border-bottom:1px solid #1b2533;}
.header-inner{display:flex;justify-content:space-between;padding:15px 0;}
.breadcrumb{font-size:14px;color:#9fb0c3;margin-bottom:20px;}
.breadcrumb a{color:#7dd3fc;}
h1{font-size:40px;line-height:1.2;}
img{max-width:100%;height:auto;border-radius:12px;margin:20px 0;}
.quick-win{background:linear-gradient(135deg,#064e3b,#065f46);padding:20px;border-radius:12px;margin:30px 0;}
.myth-fact{border:1px solid #374151;border-radius:12px;overflow:hidden;margin:30px 0;}
.myth-header{background:#991b1b;padding:10px;font-weight:bold;}
.fact-header{background:#065f46;padding:10px;font-weight:bold;}
.myth-body,.fact-body{padding:15px;}
blockquote{border-left:4px solid #3b82f6;padding-left:20px;font-style:italic;color:#bfdbfe;}
.post-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:20px;}
.post-card{background:#0b1320;border:1px solid #223247;border-radius:12px;padding:15px;}
.tag-pill{background:rgba(125,211,252,0.1);padding:2px 8px;border-radius:99px;font-size:12px;}
@media (max-width:760px){
  h1{font-size:30px;}
  .site-header{position:sticky;} /* Fix 5 */
}
"""
