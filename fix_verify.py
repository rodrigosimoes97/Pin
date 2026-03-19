"""
Corrige _write_tag_pages em site.py para gerar páginas com links de posts.
Execute na raiz do projeto: python3 fix_tag_pages.py
"""
from pathlib import Path
import subprocess

site_path = Path("src/app/site.py")
site = site_path.read_text(encoding="utf-8")

OLD = '''    tag_dir = docs_dir / "tag"
    tag_dir.mkdir(parents=True, exist_ok=True)
    tags = set(p.get("tag", "health") for p in posts)
    urls = []
    for tag in tags:
        intro = _tag_intro(tag)
        content = f"<html><head><title>{tag}</title><meta name='description' content='{escape(intro)}'><link rel='stylesheet' href='../assets/style.css'></head><body><h1>{tag}</h1></body></html>"
        (tag_dir / f"{tag}.html").write_text(content, encoding="utf-8")
        urls.append(f"tag/{tag}.html")
    return urls'''

NEW = '''    public_base = _effective_base_url(base_url)
    tag_dir = docs_dir / "tag"
    tag_dir.mkdir(parents=True, exist_ok=True)
    from collections import defaultdict
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for post in posts:
        grouped[post.get("tag", "health")].append(post)
    urls = []
    for tag, group in grouped.items():
        intro = _tag_intro(tag)
        file_name = f"{tag}.html"
        urls.append(f"tag/{file_name}")
        sorted_posts = sorted(group, key=lambda p: p.get("date", ""), reverse=True)
        post_links = "".join(
            f"<article class='post-card'>"
            f"<a href='../{p[\'url\']}'>"
            f"<h3>{escape(p[\'title\'])}</h3>"
            f"<p class='meta'>{escape(p.get(\'date\', \'\'))}</p>"
            f"</a></article>"
            for p in sorted_posts
        )
        other_tags = "".join(
            f"<a class='tag-pill' href='{escape(t)}.html'>{escape(t)}</a>"
            for t in grouped.keys() if t != tag
        )
        content = (
            f"<!doctype html><html lang='en'><head>"
            f"<meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width, initial-scale=1'>"
            f"<title>{escape(tag.title())} | {escape(site_title)}</title>"
            f"<meta name='description' content='{escape(intro)}'>"
            f"<meta name='robots' content='index,follow'>"
            f"<link rel='canonical' href='{public_base}/tag/{escape(file_name)}'>"
            f"<link rel='preconnect' href='https://fonts.googleapis.com'>"
            f"<link href='https://fonts.googleapis.com/css2?family=Lora:wght@400;600&family=DM+Sans:wght@400;500&display=swap' rel='stylesheet'>"
            f"<link rel='stylesheet' href='../assets/style.css'>"
            f"</head><body>"
            f"<header class='site-header'>"
            f"<div class='header-inner'>"
            f"<a class='site-title' href='../index.html'>{escape(site_title)}</a>"
            f"</div></header>"
            f"<main class='container'>"
            f"<div class='tag-hero'>"
            f"<p><a href='../index.html'>← Back to home</a></p>"
            f"<h1>{escape(tag.title())} hub</h1>"
            f"<p>{escape(intro)}</p>"
            f"</div>"
            f"<div class='post-grid'>{post_links}</div>"
            f"<div class='tag-row' style='margin-top:32px'>{other_tags}</div>"
            f"</main>"
            f"<footer class='site-footer'>"
            f"<div class='footer-links'>"
            f"<a href='../index.html'>Home</a>"
            f"<a href='../sitemap.xml'>Sitemap</a>"
            f"</div>"
            f"<p>Educational only — not medical advice.</p>"
            f"</footer>"
            f"</body></html>"
        )
        (tag_dir / file_name).write_text(content, encoding="utf-8")
    return urls'''

if OLD in site:
    site = site.replace(OLD, NEW)
    site_path.write_text(site, encoding="utf-8")
    print("OK site.py — _write_tag_pages corrigido")
else:
    print("ERRO: bloco nao encontrado. Verifique se o site.py mudou.")
    raise SystemExit(1)

print("\n=== Rodando verify_seo ===")
result = subprocess.run(
    ["python", "-m", "src.app.verify_seo"],
    capture_output=True, text=True,
)
print(result.stdout)
if result.stderr:
    print("STDERR:", result.stderr[:800])