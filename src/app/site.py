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

    recent_links = [f"{p['slug']}.html" for p in posts[:3]]
    html = _inject_internal_links(post["html"], recent_links)

    page = _render_post_html(base_url, site_title, post, hero_path_rel, html, run_date)
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
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
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


def _render_post_html(
    base_url: str,
    site_title: str,
    post: dict[str, str],
    hero: str,
    html: str,
    run_date: date,
) -> str:
    canonical = f"{base_url}/{post['slug']}.html"
    title = post["title"].strip()
    meta = (post.get("meta_description") or "").strip()
    alt = (post.get("alt_text") or title).strip()

    # Optional: if your content pipeline sets these keys for offer posts
    offer_name = (post.get("offer_name") or "").strip()
    offer_link = (post.get("offer_link") or "").strip()
    is_offer = bool(offer_link)

    offer_box = ""
    if is_offer:
        offer_box = f"""
        <section class="callout" aria-label="Disclosure and recommended resource">
          <strong>Recommended resource</strong>
          <p class="muted">Disclosure: This page may contain affiliate links.</p>
          <p><a class="btn" href="{offer_link}" rel="nofollow sponsored noopener" target="_blank">
            {offer_name or "Check it here"} →
          </a></p>
        </section>
        """

    # Basic OG tags (helps sharing, not ranking)
    og_image = f"{base_url}/{hero.lstrip('./')}" if not hero.startswith("http") else hero

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_escape_html(title)}</title>
  <meta name="description" content="{_escape_attr(meta)}">
  <link rel="canonical" href="{canonical}">
  <meta name="robots" content="index,follow">

  <meta property="og:type" content="article">
  <meta property="og:title" content="{_escape_attr(title)}">
  <meta property="og:description" content="{_escape_attr(meta)}">
  <meta property="og:url" content="{canonical}">
  <meta property="og:image" content="{_escape_attr(og_image)}">

  <style>
    :root {{
      --bg:#0b0f14;
      --card:#0f1720;
      --text:#e8eef5;
      --muted:#a9b4c0;
      --line:#1f2a37;
      --accent:#7dd3fc;
      --accent2:#22c55e;
    }}
    *{{box-sizing:border-box}}
    body{{
      margin:0;
      background:var(--bg);
      color:var(--text);
      font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif;
      line-height:1.75;
      font-size:17px;
      -webkit-font-smoothing: antialiased;
      text-rendering: optimizeLegibility;
    }}
    a{{color:var(--accent); text-decoration:none}}
    a:hover{{text-decoration:underline}}
    .wrap{{max-width:880px; margin:0 auto; padding:18px 14px 60px}}
    .topbar{{display:flex; align-items:center; justify-content:space-between; gap:12px; margin-bottom:14px}}
    .brand a{{color:var(--text); font-weight:700}}
    .brand small{{display:block; color:var(--muted); font-weight:400; margin-top:2px; font-size:12px}}
    .card{{
      background:var(--card);
      border:1px solid var(--line);
      border-radius:18px;
      padding:18px;
      box-shadow:0 10px 28px rgba(0,0,0,.28);
    }}
    h1{{font-size:clamp(28px, 4.6vw, 42px); line-height:1.15; margin:8px 0 10px; letter-spacing:-0.02em}}
    .meta{{color:var(--muted); font-size:14px; margin:0 0 14px}}
    .hero{{width:100%; height:auto; border-radius:14px; display:block; margin:12px 0 18px; max-height:520px; object-fit:cover}}
    .content h2{{margin:26px 0 10px; font-size:22px; line-height:1.25}}
    .content h3{{margin:18px 0 8px; font-size:18px}}
    .content p{{margin:0 0 14px}}
    .content ul, .content ol{{padding-left:20px; margin: 0 0 14px}}
    .content li{{margin:8px 0}}
    .content blockquote{{margin:16px 0; padding:12px 14px; border-left:3px solid var(--accent); background:rgba(125,211,252,.08); border-radius:12px}}
    .callout{{margin:18px 0; padding:14px 14px; border-radius:14px; border:1px solid rgba(34,197,94,.35); background:rgba(34,197,94,.08)}}
    .muted{{color:var(--muted)}}
    .btn{{display:inline-block; padding:10px 12px; border-radius:12px; background:rgba(125,211,252,.16); border:1px solid rgba(125,211,252,.35)}}
    .footer{{margin-top:22px; padding-top:16px; border-top:1px solid var(--line); color:var(--muted); font-size:14px; display:flex; flex-wrap:wrap; gap:12px; justify-content:space-between}}
    @media (prefers-color-scheme: light){{
      :root{{--bg:#f6f7fb; --card:#ffffff; --text:#0b1220; --muted:#5b6777; --line:#e5e7eb; --accent:#0369a1; --accent2:#16a34a;}}
      .card{{box-shadow:0 8px 22px rgba(15,23,42,.08);}}
      .btn{{background:rgba(3,105,161,.08); border:1px solid rgba(3,105,161,.25)}}
    }}
  </style>
</head>

<body>
  <div class="wrap">
    <div class="topbar">
      <div class="brand">
        <a href="index.html">{_escape_html(site_title)}</a>
        <small>Educational health content for US readers</small>
      </div>
      <div><a href="{base_url}/sitemap.xml">Sitemap</a></div>
    </div>

    <div class="card">
      <p class="meta"><em>Educational only — not medical advice.</em> • Updated: {run_date.isoformat()}</p>
      <h1>{_escape_html(title)}</h1>

      <img class="hero" src="{hero}" alt="{_escape_attr(alt)}" loading="lazy">

      <div class="content">
        {html}
      </div>

      {offer_box}

      <div class="footer">
        <div><a href="index.html">← Back to home</a></div>
        <div><a href="{canonical}">Permalink</a></div>
      </div>
    </div>
  </div>
</body>
</html>"""


def _write_index(docs_dir: Path, base_url: str, site_title: str, posts: list[dict[str, str]]) -> None:
    items = []
    for p in posts[:60]:
        title = _escape_html(p["title"])
        desc = _escape_html((p.get("description") or "")[:160])
        items.append(
            f"""
            <li class="item">
              <a class="t" href="{p['url']}">{title}</a>
              <div class="d">{desc}</div>
              <div class="m">{p['date']}</div>
            </li>
            """.strip()
        )
    items_html = "\n".join(items)

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_escape_html(site_title)}</title>
  <meta name="description" content="Fresh US health content: recipes, home workouts, habits, and practical wellness tips.">
  <link rel="canonical" href="{base_url}/index.html">
  <style>
    :root{{--bg:#0b0f14;--card:#0f1720;--text:#e8eef5;--muted:#a9b4c0;--line:#1f2a37;--accent:#7dd3fc}}
    *{{box-sizing:border-box}}
    body{{margin:0;background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif;line-height:1.7;font-size:17px}}
    a{{color:var(--accent);text-decoration:none}} a:hover{{text-decoration:underline}}
    .wrap{{max-width:880px;margin:0 auto;padding:18px 14px 60px}}
    .card{{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:18px;box-shadow:0 10px 28px rgba(0,0,0,.28)}}
    h1{{font-size:clamp(26px,4.2vw,38px);margin:8px 0 6px}}
    .sub{{color:var(--muted);margin:0 0 14px}}
    ul{{list-style:none;padding:0;margin:0}}
    .item{{padding:14px 0;border-top:1px solid var(--line)}}
    .item:first-child{{border-top:none}}
    .t{{display:block;font-weight:700;font-size:18px;margin-bottom:6px}}
    .d{{color:var(--muted);font-size:14px;margin-bottom:6px}}
    .m{{color:var(--muted);font-size:12px}}
    .top{{display:flex;justify-content:space-between;gap:12px;align-items:center;margin-bottom:12px}}
    @media (prefers-color-scheme: light){{
      :root{{--bg:#f6f7fb;--card:#ffffff;--text:#0b1220;--muted:#5b6777;--line:#e5e7eb;--accent:#0369a1}}
      .card{{box-shadow:0 8px 22px rgba(15,23,42,.08)}}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="top">
      <div>
        <h1>{_escape_html(site_title)}</h1>
        <p class="sub">Recipes, home workouts, habits, and practical wellness tips. Educational only.</p>
      </div>
      <div><a href="{base_url}/sitemap.xml">Sitemap</a></div>
    </div>

    <div class="card">
      <ul>
        {items_html}
      </ul>
    </div>
  </div>
</body>
</html>"""
    (docs_dir / "index.html").write_text(html, encoding="utf-8")


def _write_sitemap(docs_dir: Path, base_url: str, posts: list[dict[str, str]]) -> None:
    rows = [f"<url><loc>{base_url}/index.html</loc></url>"]
    rows.extend(f"<url><loc>{base_url}/{p['url']}</loc></url>" for p in posts[:200])
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


def _escape_html(s: str) -> str:
    return (
        (s or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def _escape_attr(s: str) -> str:
    # same as html escape; kept separate for clarity
    return _escape_html(s)
