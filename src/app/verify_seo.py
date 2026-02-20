from __future__ import annotations

import re
import tempfile
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from pathlib import Path

from .site import publish_post


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def run_checks() -> None:
    with tempfile.TemporaryDirectory() as td:
        docs = Path(td)
        base_url = "https://rodrigosimoes97.github.io/Pin"

        for i in range(10):
            post = {
                "slug": f"sleep-post-{i}",
                "title": f"Sleep Post {i}",
                "meta_description": "Practical sleep guidance for better nightly recovery.",
                "html": (
                    "<p>Short answer sentence one. Sentence two.</p>"
                    "<h2>Step One</h2><p>Do this.</p>"
                    "<h2>FAQ</h2><h3>What helps sleep?</h3><p>A routine helps.</p>"
                    "<p><a href='#recent-1'>A</a> <a href='#recent-2'>B</a> <a href='#recent-3'>C</a> "
                    "<a href='#recent-4'>D</a> <a href='#recent-5'>E</a></p>"
                ),
                "image_query": "sleep bedroom",
                "pin_title": "Pin",
                "pin_description": "Pin desc",
                "alt_text": "Sleep image",
                "tag": "sleep",
            }
            publish_post(
                docs_dir=docs,
                base_url=base_url,
                site_title="Practical US Health Notes",
                post=post,
                hero_path_rel=f"assets/sleep-{i}.jpg",
                run_date=date(2026, 1, 1) + timedelta(days=i),
            )

        sitemap = docs / "sitemap.xml"
        tree = ET.parse(sitemap)
        root = tree.getroot()
        _assert(root.tag.endswith("urlset"), "sitemap root must be <urlset>")
        locs = root.findall("{http://www.sitemaps.org/schemas/sitemap/0.9}url/{http://www.sitemaps.org/schemas/sitemap/0.9}loc")
        _assert(bool(locs), "sitemap must contain <loc> entries")

        post_html = (docs / "sleep-post-9.html").read_text(encoding="utf-8")
        checks = [
            "<title>",
            "meta name='description'",
            "rel='canonical'",
            "property='og:title'",
            "property='og:description'",
            "property='og:image'",
            "property='og:url'",
            "property='og:type' content='article'",
            "name='twitter:card' content='summary_large_image'",
            "name='twitter:title'",
            "name='twitter:description'",
            "name='twitter:image'",
            '"@type": "Article"',
            '"@type": "FAQPage"',
            '"@type": "BreadcrumbList"',
        ]
        for needle in checks:
            _assert(needle in post_html, f"missing post SEO marker: {needle}")

        tag_html = (docs / "tag" / "sleep.html").read_text(encoding="utf-8")
        _assert("Explore practical sleep guides" in tag_html, "tag intro missing")
        links = re.findall(r"href='../[^']+\.html'", tag_html)
        _assert(len(links) >= 8, "tag page should contain at least 8 post links when available")

    print("SEO verification passed")


if __name__ == "__main__":
    run_checks()
