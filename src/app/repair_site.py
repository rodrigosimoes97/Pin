from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from . import site as site_mod


HREF_RE = re.compile(r"""href\s*=\s*(['"])([^'"]+)\1""", re.IGNORECASE)


def _load_posts(posts_path: Path) -> list[dict[str, Any]]:
    if not posts_path.exists():
        return []
    try:
        data = json.loads(posts_path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def _existing_html_set(docs_dir: Path) -> set[str]:
    return {p.name for p in docs_dir.glob("*.html")}


def _rewrite_broken_local_html_links(file_path: Path, existing: set[str]) -> bool:
    """
    Replace href="missing.html" (local) with href="index.html".
    Only touches links that look like local *.html (no http, no mailto, no anchors).
    Returns True if file changed.
    """
    text = file_path.read_text(encoding="utf-8", errors="ignore")
    original = text

    def repl(m: re.Match[str]) -> str:
        quote = m.group(1)
        href = m.group(2).strip()

        if href.startswith(("http://", "https://", "mailto:", "tel:")):
            return m.group(0)
        if href.startswith("#"):
            return m.group(0)

        href_clean = href.split("#", 1)[0].split("?", 1)[0].strip()
        if not href_clean.lower().endswith(".html"):
            return m.group(0)

        # handle ../ for tag pages
        candidate = href_clean
        if candidate.startswith("../"):
            candidate_name = candidate.replace("../", "", 1)
            if candidate_name not in existing:
                return f"href={quote}../index.html{quote}"
            return m.group(0)

        # normal local html
        if candidate not in existing:
            return f"href={quote}index.html{quote}"
        return m.group(0)

    text = HREF_RE.sub(repl, text)

    if text != original:
        file_path.write_text(text, encoding="utf-8")
        return True
    return False


def main() -> None:
    docs_dir = Path("docs")
    posts_path = docs_dir / "posts.json"
    posts = _load_posts(posts_path)

    existing = _existing_html_set(docs_dir)

    # 1) Drop posts.json entries whose html file doesn't exist
    filtered = []
    for p in posts:
        slug = (p.get("slug") or "").strip()
        url = (p.get("url") or f"{slug}.html").strip()
        if not url:
            continue
        if url in existing:
            filtered.append(p)

    if filtered != posts:
        posts_path.write_text(json.dumps(filtered[:200], indent=2), encoding="utf-8")

    # 2) Rewrite broken local links inside all docs/*.html
    changed_files = 0
    for html_file in docs_dir.glob("*.html"):
        if _rewrite_broken_local_html_links(html_file, existing):
            changed_files += 1

    # 3) Also fix tag pages links (../missing.html)
    tag_dir = docs_dir / "tag"
    if tag_dir.exists():
        for html_file in tag_dir.glob("*.html"):
            if _rewrite_broken_local_html_links(html_file, existing):
                changed_files += 1

    # 4) Rebuild index/tag/sitemap/robots from cleaned posts.json
    base_url = (Path(".") / ".base_url.tmp").read_text().strip() if (Path(".") / ".base_url.tmp").exists() else ""
    # Prefer env if running in Actions
    import os
    base_url = (os.getenv("BASE_URL") or base_url).strip().rstrip("/")
    if not base_url:
        raise SystemExit("BASE_URL missing. Set env BASE_URL for repair_site.")

    site_title = (os.getenv("SITE_TITLE") or "Practical US Health Notes").strip()

    # write_site_state regenerates index/tag/sitemap/robots
    site_mod.write_site_state(docs_dir, base_url, site_title, filtered)

    print(f"repair_site: posts kept={len(filtered)} html_changed={changed_files}")


if __name__ == "__main__":
    main()
