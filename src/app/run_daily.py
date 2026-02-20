from __future__ import annotations

import json
import logging
import random
from datetime import datetime, timezone

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

LOG = logging.getLogger(__name__)


def _setup_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")


def _choose_mode(state: dict) -> str:
    runs = int(state.get("runs", 0))
    offer_runs = int(state.get("offer_runs", 0))
    if runs == 0:
        return "info"
    ratio = offer_runs / max(runs, 1)
    if ratio < 0.30:
        return "offer" if random.random() < 0.6 else "info"
    return "offer" if random.random() < 0.15 else "info"


def _pick_offer(repo_root, topic_tag: str) -> dict | None:
    offers = json.loads((repo_root / "offers.json").read_text(encoding="utf-8"))
    compatible = [item for item in offers if topic_tag in item.get("tags", []) or "us" in item.get("tags", [])]
    return random.choice(compatible or offers) if offers else None


def _should_generate_today(posts_per_week: int) -> bool:
    if posts_per_week >= 7:
        return True
    return datetime.now(timezone.utc).weekday() < posts_per_week


def main() -> None:
    _setup_logging()
    settings = load_settings()
    if not _should_generate_today(settings.posts_per_week):
        LOG.info("Skipping generation today to maintain %s posts/week.", settings.posts_per_week)
        return

    today = datetime.now(timezone.utc).date()
    state_path = settings.repo_root / "generated" / "state.json"
    state = load_state(state_path)

    topic = pick_topic(state.get("recent_topics", []))
    mode = _choose_mode(state)
    offer = _pick_offer(settings.repo_root, topic.tag) if mode == "offer" else None

    client = GeminiClient(api_keys=settings.gemini_api_keys, model=settings.gemini_model)
    titles = generate_titles(client, topic)
    chosen_title = pick_best_title(titles)
    post = generate_article(client, topic, chosen_title, mode, offer)
    post["tag"] = normalize_tag(post.get("tag", "")) or normalize_tag(topic.tag) or "health"

    recent_slugs = set(state.get("recent_slugs", [])[-40:])
    if post["slug"] in recent_slugs:
        post["slug"] = f"{post['slug']}-{today.strftime('%m%d')}"

    hero_rel = f"assets/{today.isoformat()}_{post['slug']}.jpg"
    fetch_hero_image(settings.pexels_api_key, post["image_query"], settings.repo_root / "docs" / hero_rel)

    pin_rel = f"generated/pinterest/{today.isoformat()}_{post['slug']}.png"
    create_pinterest_image(settings.pexels_api_key, post["image_query"], post["pin_title"], settings.repo_root / pin_rel)

    record = publish_post(
        docs_dir=settings.repo_root / "docs",
        base_url=settings.base_url,
        site_title=settings.site_title,
        post=post,
        hero_path_rel=hero_rel,
        run_date=today,
    )
    post_link = f"{settings.base_url}/{record['url']}"
    write_draft_pack(
        out_dir=settings.repo_root / "generated" / "pinterest",
        run_date=today,
        pin_title=post["pin_title"],
        pin_description=post["pin_description"],
        link=post_link,
        image_path=pin_rel,
        alt_text=post["alt_text"],
    )

    if settings.pinterest_enable_publish and settings.pinterest_access_token and settings.pinterest_board_id:
        create_pin(
            access_token=settings.pinterest_access_token,
            board_id=settings.pinterest_board_id,
            title=post["pin_title"],
            description=post["pin_description"],
            link=post_link,
            image_url=f"{settings.base_url}/{hero_rel}",
            alt_text=post["alt_text"],
            log_path=settings.repo_root / "generated" / "logs" / "pinterest.log",
        )

    state["runs"] = int(state.get("runs", 0)) + 1
    state["offer_runs"] = int(state.get("offer_runs", 0)) + (1 if mode == "offer" else 0)
    state["recent_topics"] = (state.get("recent_topics", []) + [topic.slug])[-30:]
    state["recent_slugs"] = (state.get("recent_slugs", []) + [post["slug"]])[-80:]
    state["last_run"] = today.isoformat()
    save_state(state_path, state)

    LOG.info("Published %s (%s) tag=%s", record["url"], mode, post["tag"])


if __name__ == "__main__":
    main()
