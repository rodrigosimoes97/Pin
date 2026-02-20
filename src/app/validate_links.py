from __future__ import annotations

import re
from pathlib import Path

HREF_RE = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE)


def _iter_html_files(docs_dir: Path) -> list[Path]:
    files = list(docs_dir.glob("*.html"))
    files.extend(docs_dir.glob("tag/*.html"))
    return files


def validate_links(docs_dir: Path) -> list[str]:
    errors: list[str] = []
    docs_root = docs_dir.resolve()

    for html_file in _iter_html_files(docs_dir):
        content = html_file.read_text(encoding="utf-8")
        for href in HREF_RE.findall(content):
            if href.startswith(("http://", "https://", "mailto:", "tel:", "#")):
                continue
            if not href.endswith(".html"):
                continue

            if href.startswith('/'):
                target = (docs_root / href.lstrip('/')).resolve()
            else:
                target = (html_file.parent / href).resolve()
            if docs_root not in [target, *target.parents]:
                errors.append(f"{html_file}: link escapes docs -> {href}")
                continue
            if not target.exists():
                errors.append(f"{html_file}: missing target -> {href}")

    return errors


def main() -> None:
    docs_dir = Path(__file__).resolve().parents[2] / "docs"
    errors = validate_links(docs_dir)
    if errors:
        for err in errors:
            print(err)
        raise SystemExit(1)
    print("Link validation passed")


if __name__ == "__main__":
    main()
