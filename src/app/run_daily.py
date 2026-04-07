from __future__ import annotations

import json
import logging
import random
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import load_settings
from .content import generate_article, normalize_tag
from .gemini_client import GeminiClient
from .images import create_pinterest_image, fetch_hero_image
from .pinterest_api import create_pin
from .pinterest_drafts import write_draft_pack
from .site import publish_post
from .state import load_state, save_state
from .titles import generate_titles, pick_best_title
from .topics import pick_topic
from .duplicate_checker import DuplicateChecker
from .trend_research import get_trending_topics
from .topics import Topic, PRIORITY_TAGS
from .internal_links import get_related_internal_links
from .indexing import index_new_post

LOG = logging.getLogger(__name__)

def _setup_logging(repo_root: Path) -> None:
    log_dir = repo_root / "generated" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
        handlers=[
            logging.FileHandler(log_dir / "system.log", encoding="utf-8"),
            logging.StreamHandler()
        ]
    )
    # Silence noisy logs
    logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("huggingface_hub").setLevel(logging.WARNING)

def _log_to_file(repo_root: Path, filename: str, message: str) -> None:
    log_dir = repo_root / "generated" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    with open(log_dir / filename, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now(timezone.utc).isoformat()} - {message}\n")

def _validate_quality(post: dict[str, Any], topic_name: str) -> bool:
    """Checks word count and keyword presence."""
    text = re.sub(r'<[^>]+>', ' ', post.get("html", ""))
    word_count = len(text.split())
    
    if word_count < 450: # Slightly lower threshold to be safe but target 500
        LOG.warning("Quality check failed: word count %d < 450", word_count)
        return False
        
    topic_name_lower = topic_name.lower()
    if topic_name_lower not in post.get("title", "").lower() and topic_name_lower not in text.lower():
        LOG.warning("Quality check failed: keyword '%s' not found in title or body", topic_name)
        return False
        
    return True

def _create_topic_from_trend(client: GeminiClient, trend: str) -> Topic:
    prompt = f"""Analyze this trending health topic: '{trend}'
Categorize it into one of these tags: {', '.join(PRIORITY_TAGS)}
Return a JSON object with:
- slug: a URL-friendly version of the topic
- name: a catchy, SEO-friendly name
- angle: a unique angle for a health article (US-focused, conversational)
- tag: the chosen tag from the list
Strict JSON only.
"""
    try:
        data = client.generate_json(prompt)
        return Topic(
            slug=str(data.get("slug", "")),
            name=str(data.get("name", "")),
            angle=str(data.get("angle", "")),
            tag=str(data.get("tag", "health")),
        )
    except Exception as e:
        LOG.warning("Failed to create topic from trend '%s': %s", trend, e)
        return Topic(
            slug=trend.lower().replace(" ", "-")[:50],
            name=trend,
            angle="latest insights and practical tips for daily health",
            tag="health",
        )

def _choose_mode(state: dict) -> str:
    runs = int(state.get("runs", 0))
    offer_runs = int(state.get("offer_runs", 0))
    if runs == 0:
        return "info"
    ratio = offer_runs / max(runs, 1)
    if ratio < 0.30:
        return "offer" if random.random() < 0.6 else "info"
    return "offer" if random.random() < 0.15 else "info"

def _pick_offer(repo_root: Path, topic_tag: str) -> dict | None:
    offers_path = repo_root / "offers.json"
    if not offers_path.exists(): return None
    offers = json.loads(offers_path.read_text(encoding="utf-8"))
    compatible = [item for item in offers if topic_tag in item.get("tags", []) or "us" in item.get("tags", [])]
    return random.choice(compatible or offers) if offers else None

def _should_generate_today(posts_per_week: int) -> bool:
    if posts_per_week >= 7: return True
    return datetime.now(timezone.utc).weekday() < posts_per_week

def main() -> None:
    settings = load_settings()
    _setup_logging(settings.repo_root)
    
    if not _should_generate_today(settings.posts_per_week):
        LOG.info("Skipping generation today to maintain %s posts/week.", settings.posts_per_week)
        return

    today = datetime.now(timezone.utc).date()
    state_path = settings.repo_root / "generated" / "state.json"
    state = load_state(state_path)

    client = GeminiClient(api_keys=settings.gemini_api_keys, model=settings.gemini_model)
    checker = DuplicateChecker(index_path=settings.repo_root / "generated" / "content_index.json")

    # Fetch and log trending topics
    LOG.info("Fetching trending topics for USA...")
    trends = get_trending_topics()
    for trend in trends:
        _log_to_file(settings.repo_root, "trends.log", f"Found trend: {trend}")

    recent_topics = list(state.get("recent_topics", []))
    recent_tags = list(state.get("recent_tags", []))
    recent_slugs = list(state.get("recent_slugs", []))
    recent_titles = list(state.get("recent_titles", []))
    tag_counts = dict(state.get("tag_counts", {}))
    topic_rotation = dict(state.get("topic_rotation", {}))
    daily_slugs: set[str] = set()
    daily_topics: set[str] = set()
    published_count = 0

    posts_json_path = settings.repo_root / "docs" / "posts.json"
    existing_posts = []
    if posts_json_path.exists():
        existing_posts = json.loads(posts_json_path.read_text(encoding="utf-8"))

    for slot in range(5):
        mode = _choose_mode(state)
        topic = None
        for trend in list(trends):
            temp_slug = trend.lower().replace(" ", "-")[:50]
            if temp_slug not in recent_topics and temp_slug not in daily_topics:
                LOG.info("Using trending topic: %s", trend)
                topic = _create_topic_from_trend(client, trend)
                trends.remove(trend)
                break

        if not topic:
            topic = pick_topic(
                recent_topics=recent_topics,
                recent_tags=recent_tags,
                tag_counts=tag_counts,
                excluded_slugs=daily_topics,
                topic_rotation=topic_rotation,
            )

        offer = _pick_offer(settings.repo_root, topic.tag) if mode == "offer" else None

        try:
            titles = generate_titles(client, topic, excluded_titles=recent_titles)
            chosen_title = pick_best_title(titles)

            post = None
            for attempt in range(3):
                candidate = generate_article(client, topic, chosen_title, mode, offer)
                candidate["tag"] = normalize_tag(candidate.get("tag", "")) or normalize_tag(topic.tag) or "health"

                if not _validate_quality(candidate, topic.name):
                    continue

                status, score = checker.check_similarity(candidate["title"], candidate["meta_description"], candidate["html"])
                if status == "BLOCK":
                    _log_to_file(settings.repo_root, "duplicate_blocked.log", f"BLOCKED: {candidate['title']} (score: {score})")
                    break
                if status == "REWRITE":
                    continue

                post = candidate
                checker.add_to_index(post["title"], post["slug"], post["meta_description"], post["html"])
                break

            if not post: continue

            # Internal linking
            related_for_links = get_related_internal_links(post["html"], existing_posts, post["slug"])
            if related_for_links:
                # Add a "Recommended Reading" section at the end of HTML
                links_html = "<h3>Recommended Reading</h3><ul>"
                for rel in related_for_links:
                    links_html += f"<li><a href='{rel['url']}'>{rel['title']}</a></li>"
                links_html += "</ul>"
                post["html"] += links_html

            if post["slug"] in set(recent_slugs[-40:]) or post["slug"] in daily_slugs:
                post["slug"] = f"{post['slug']}-{today.strftime('%m%d')}-{slot + 1}"

            hero_rel = f"assets/{today.isoformat()}_{post['slug']}.webp"
            fetch_hero_image(settings.pexels_api_key, post["image_query"], settings.repo_root / "docs" / hero_rel)

            pin_rel = f"generated/pinterest/{today.isoformat()}_{post['slug']}.png"
            create_pinterest_image(settings.pexels_api_key, post["image_query"], post["pin_title"], settings.repo_root / pin_rel, source_image_path=settings.repo_root / "docs" / hero_rel)

            record = publish_post(docs_dir=settings.repo_root / "docs", base_url=settings.base_url, site_title=settings.site_title, post=post, hero_path_rel=hero_rel, run_date=today)
            
            # Google Indexing
            post_url = f"{settings.base_url}/{record['url']}"
            if settings.google_indexing_json_path:
                LOG.info("Submitting URL to Google Indexing: %s", post_url)
                index_new_post(settings.repo_root, settings.google_indexing_json_path, post_url)

            _log_to_file(settings.repo_root, "published_posts.log", f"Published: {record['url']} ({mode})")

            daily_slugs.add(post["slug"])
            daily_topics.add(topic.slug)
            published_count += 1
            recent_topics.append(topic.slug)
            recent_tags.append(post["tag"])
            recent_slugs.append(post["slug"])
            recent_titles.append(chosen_title)
            tag_counts[post["tag"]] = int(tag_counts.get(post["tag"], 0)) + 1
            topic_rotation[topic.tag] = int(topic_rotation.get(topic.tag, 0)) + 1

            LOG.info("Published %s (%s)", record["url"], mode)
        except Exception:
            LOG.exception("Failed slot %s", slot + 1)

    state.update({
        "runs": int(state.get("runs", 0)) + 1,
        "recent_topics": recent_topics[-50:],
        "recent_tags": recent_tags[-50:],
        "recent_slugs": recent_slugs[-100:],
        "recent_titles": recent_titles[-60:],
        "tag_counts": tag_counts,
        "topic_rotation": topic_rotation,
        "last_run": today.isoformat()
    })
    save_state(state_path, state)
    LOG.info("Run complete. Published %s/5 posts.", published_count)

if __name__ == "__main__":
    main()
