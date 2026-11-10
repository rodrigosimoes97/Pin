from __future__ import annotations

import re
from pathlib import Path

HREF_RE = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE)


def _iter_html_files(docs_dir: Path) -> list[Path]:
    files = list(docs_dir.glob("*.html"))
    files.extend(docs_dir.glob("tag/*.html"))
    return files


def _resolve_target(docs_root: Path, current_file: Path, href: str) -> Path | None:
    # Remove fragment e query string
    clean_href = href.split("#", 1)[0].split("?", 1)[0].strip()
    if not clean_href:
        return None

    # Normaliza caminhos raiz ou relativos
    if clean_href == "/":
        return docs_root / "index.html"

    if clean_href.startswith("/"):
        rel_path = clean_href.lstrip("/")
        # Verifica se já aponta para arquivo com extensão (ex: assets/style.css, sitemap.xml)
        direct_target = (docs_root / rel_path).resolve()
        if direct_target.exists():
            return direct_target
        # Se for URL limpa sem extensão (ex: /about ou /tag/sleep ou /meu-post), busca .html
        html_target = (docs_root / f"{rel_path}.html").resolve()
        return html_target

    # Link relativo
    direct_rel = (current_file.parent / clean_href).resolve()
    if direct_rel.exists():
        return direct_rel
    html_rel = (current_file.parent / f"{clean_href}.html").resolve()
    return html_rel


def validate_links(docs_dir: Path) -> list[str]:
    errors: list[str] = []
    docs_root = docs_dir.resolve()

    for html_file in _iter_html_files(docs_dir):
        content = html_file.read_text(encoding="utf-8")
        for href in HREF_RE.findall(content):
            trimmed = href.strip()
            # Ignora links externos, âncoras puras, javascript, mailto, tel
            if trimmed.startswith(("http://", "https://", "mailto:", "tel:", "#", "javascript:")):
                continue

            target = _resolve_target(docs_root, html_file, trimmed)
            if target is None:
                continue

            if docs_root not in [target, *target.parents]:
                errors.append(f"{html_file.name}: link escapes docs -> {trimmed}")
                continue

            if not target.exists():
                errors.append(f"{html_file.name}: missing target -> {trimmed} (resolved to {target.name})")

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
