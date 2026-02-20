from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Iterable, Set, Tuple


HREF_RE = re.compile(r"""href\s*=\s*["']([^"']+)["']""", re.IGNORECASE)


def _iter_html_files(docs_dir: Path) -> Iterable[Path]:
    yield from docs_dir.glob("*.html")
    tag_dir = docs_dir / "tag"
    if tag_dir.exists():
        yield from tag_dir.glob("*.html")


def _normalize_target(current_file: Path, href: str) -> Path | None:
    href = href.strip()
    if not href:
        return None

    # Ignore anchors
    if href.startswith("#"):
        return None

    # Ignore mailto/tel
    if href.startswith("mailto:") or href.startswith("tel:"):
        return None

    # Ignore external links
    if href.startswith("http://") or href.startswith("https://"):
        return None

    # Ignore non-html assets
    if any(href.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp", ".svg", ".css", ".js", ".pdf"]):
        return None

    # Strip query/fragment
    href = href.split("#", 1)[0].split("?", 1)[0].strip()
    if not href:
        return None

    # We only validate local .html links (index.html, tag/*.html, post.html)
    if not href.lower().endswith(".html"):
        return None

    # Resolve relative to current file location
    base = current_file.parent
    return (base / href).resolve()


def validate_links(docs_dir: Path) -> Tuple[bool, Set[str]]:
    docs_dir = docs_dir.resolve()
    errors: Set[str] = set()

    for html_file in _iter_html_files(docs_dir):
        text = html_file.read_text(encoding="utf-8", errors="ignore")
        for href in HREF_RE.findall(text):
            target = _normalize_target(html_file, href)
            if target is None:
                continue

            # Ensure target stays inside docs_dir
            if not str(target).startswith(str(docs_dir)):
                errors.add(f"{html_file.relative_to(docs_dir)} -> {href} (escapes docs dir)")
                continue

            if not target.exists():
                # Show a nice relative path
                try:
                    rel_target = target.relative_to(docs_dir)
                except Exception:
                    rel_target = target
                errors.add(f"{html_file.relative_to(docs_dir)} -> {href} (missing: {rel_target})")

    return (len(errors) == 0), errors


def main() -> None:
    ap = argparse.ArgumentParser(description="Validate internal HTML links in docs/ (GitHub Pages).")
    ap.add_argument("--docs-dir", default="docs", help="Docs directory. Default: docs")
    args = ap.parse_args()

    ok, errors = validate_links(Path(args.docs_dir))
    if ok:
        print("OK: No broken internal HTML links found.")
        return

    print("BROKEN LINKS FOUND:")
    for e in sorted(errors):
        print(" -", e)
    raise SystemExit(1)


if __name__ == "__main__":
    main()
