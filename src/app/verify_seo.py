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
        base_url = "https://health-ptg.pages.dev"

        for i in range(10):
            post = {
                "slug": f"sleep-post-{i}",
                "title": f"Sleep Post {i}",
                "meta_description": f"Practical evidence-informed sleep guidance for better nightly recovery {i}.",
                "html": (
                    "<p>Short answer sentence one. Sentence two.</p>"
                    "<h2>Step One</h2><p>Do this.</p>"
                    "<h2>FAQ</h2><h3>What helps sleep?</h3><p>A routine helps.</p>"
                    "<p><a href='#recent-1'>A</a> <a href='#recent-2'>B</a> <a href='#recent-3'>C</a> "
                    "<a href='#recent-4'>D</a> <a href='#recent-5'>E</a></p>"
                ),
                "image_query": "sleep bedroom",
                "pin_title": f"Sleep Post Pin Title {i} For Testing",
                "pin_description": f"Practical sleep pin description for test post {i} with actionable guidance.",
                "alt_text": "Sleep image showing bedroom setup",
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

        # 1. Sitemap XML checks
        sitemap = docs / "sitemap.xml"
        _assert(sitemap.exists(), "sitemap.xml must exist")
        tree = ET.parse(sitemap)
        root = tree.getroot()
        _assert(root.tag.endswith("urlset"), "sitemap root must be <urlset>")
        locs = root.findall("{http://www.sitemaps.org/schemas/sitemap/0.9}url/{http://www.sitemaps.org/schemas/sitemap/0.9}loc")
        _assert(bool(locs), "sitemap must contain <loc> entries")

        for loc in locs:
            url_text = str(loc.text).strip()
            _assert(not url_text.endswith(".html"), f"sitemap must NOT contain .html URLs: {url_text}")
            _assert(url_text.startswith("https://health-ptg.pages.dev"), f"unexpected base URL in sitemap: {url_text}")

        # 2. Post HTML SEO checks
        post_html = (docs / "sleep-post-9.html").read_text(encoding="utf-8")
        expected_canonical = "https://health-ptg.pages.dev/sleep-post-9"
        _assert(f"<link rel='canonical' href='{expected_canonical}'>" in post_html, "canonical link mismatch or has .html")
        _assert(f"<meta property='og:url' content='{expected_canonical}'>" in post_html, "og:url mismatch")

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

        # 3. Tag page checks
        tag_html = (docs / "tag" / "sleep.html").read_text(encoding="utf-8")
        _assert("Explore practical sleep guides" in tag_html, "tag intro missing")
        _assert("<link rel='canonical' href='https://health-ptg.pages.dev/tag/sleep'>" in tag_html, "tag canonical mismatch")
        links = re.findall(r'href=[\'"]/sleep-post-\d+[\'\"]', tag_html)
        _assert(len(links) >= 8, f"tag page should contain at least 8 clean post links, found {len(links)}")

        # 4. Robots.txt checks
        robots_txt = (docs / "robots.txt").read_text(encoding="utf-8")
        _assert("Allow: /" in robots_txt, "robots.txt must allow root")
        _assert("Sitemap: https://health-ptg.pages.dev/sitemap.xml" in robots_txt, "robots.txt must point to sitemap")

    print("SEO verification passed successfully (clean URLs, canonicals & sitemap)")


if __name__ == "__main__":
    run_checks()
