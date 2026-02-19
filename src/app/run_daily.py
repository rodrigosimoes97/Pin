from __future__ import annotations

import json
import random
from datetime import datetime, timezone
from pathlib import Path

from .config import load_settings
from .content import generate_post_json
from .images import create_pinterest_image, fetch_hero_image
from .pinterest_api import create_pin
from .pinterest_drafts import write_draft_pack
from .site import publish_post
from .topics import pick_topic


def _load_state(path: Path) -> dict:
    if not path.exists():
        return {"runs": 0, "offer_runs": 0, "recent_topics": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"runs": 0, "offer_runs": 0, "recent_topics": []}


def _choose_mode(state: dict) -> str:
    runs = int(state.get("runs", 0))
    offers = int(state.get("offer_runs", 0))
    target = 0.30
    if runs == 0:
        return "info"
    current_ratio = offers / runs
    if current_ratio < target:
        return "offer" if random.random() < 0.6 else "info"
    return "offer" if random.random() < 0.2 else "info"


def _pick_offer(repo_root: Path, topic_tag: str) -> dict | None:
    offers_path = repo_root / "offers.json"
    offers = json.loads(offers_path.read_text(encoding="utf-8"))
    tagged = [o for o in offers if topic_tag in o.get("tags", []) or "us" in o.get("tags", [])]
    if not tagged:
        return offers[0] if offers else None
    return random.choice(tagged)


def main() -> None:
    settings = load_settings()
    today = datetime.now(timezone.utc).date()

    generated = settings.repo_root / "generated"
    logs_dir = generated / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    run_log = logs_dir / f"{today.isoformat()}.log"

    state_path = generated / "state.json"
    state = _load_state(state_path)
    mode = _choose_mode(state)

    topic = pick_topic(settings.repo_root)
    offer = _pick_offer(settings.repo_root, topic["tag"]) if mode == "offer" else None

    post = generate_post_json(
        openai_api_key=settings.openai_api_key,
        model=settings.openai_model,
        mode=mode,
        topic=topic,
        offer=offer,
    )
    if mode == "offer":
        post["slug"] = f"{topic['slug']}-offer"
    else:
        post["slug"] = f"{topic['slug']}-guide"

    hero_rel = f"assets/{today.isoformat()}_{post['slug']}.jpg"
    hero_path = settings.repo_root / "docs" / hero_rel
    fetch_hero_image(settings.pexels_api_key, post["image_query"], hero_path)

    pin_rel = f"generated/pinterest/{today.isoformat()}_{post['slug']}.png"
    pin_path = settings.repo_root / pin_rel
    create_pinterest_image(settings.pexels_api_key, post["image_query"], post["pin_title"], pin_path)

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

    published = False
    if (
        settings.pinterest_enable_publish
        and settings.pinterest_access_token
        and settings.pinterest_board_id
    ):
        published = create_pin(
            access_token=settings.pinterest_access_token,
            board_id=settings.pinterest_board_id,
            title=post["pin_title"],
            description=post["pin_description"],
            link=post_link,
            image_url=f"{settings.base_url}/{post['slug']}.html",
            alt_text=post["alt_text"],
            log_path=settings.repo_root / "generated" / "logs" / "pinterest.log",
        )

    state["runs"] = int(state.get("runs", 0)) + 1
    if mode == "offer":
        state["offer_runs"] = int(state.get("offer_runs", 0)) + 1
    recent = state.get("recent_topics", [])
    recent.append(topic["slug"])
    state["recent_topics"] = recent[-30:]
    state["last_run"] = today.isoformat()
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    run_log.write_text(
        "\n".join(
            [
                f"date={today.isoformat()}",
                f"mode={mode}",
                f"topic={topic['topic']}",
                f"slug={post['slug']}",
                f"post_url={post_link}",
                f"pinterest_publish_attempted={settings.pinterest_enable_publish}",
                f"pinterest_published={published}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
