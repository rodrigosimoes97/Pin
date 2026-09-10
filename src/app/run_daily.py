from __future__ import annotations

import json
import logging
import random
import re
import time
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
from .titles import _local_title_hint  # fallback local, veja titles.py
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
            logging.StreamHandler(),
        ],
    )
    logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
    logging.getLogger("transformers").setLevel(logging.ERROR)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("huggingface_hub").setLevel(logging.ERROR)


def _log_to_file(repo_root: Path, filename: str, message: str) -> None:
    log_dir = repo_root / "generated" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    with open(log_dir / filename, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now(timezone.utc).isoformat()} - {message}\n")


def _validate_quality(post: dict[str, Any], topic_name: str) -> bool:
    """Verifica contagem de palavras e presença da keyword."""
    text = re.sub(r"<[^>]+>", " ", post.get("html", ""))
    word_count = len(text.split())

    if word_count < 450:
        LOG.warning("[Quality] word_count=%d < 450", word_count)
        return False

    topic_name_lower = topic_name.lower()
    if topic_name_lower not in post.get("title", "").lower() and topic_name_lower not in text.lower():
        LOG.warning("[Quality] keyword '%s' não encontrada no título ou corpo", topic_name)
        return False

    return True


def _local_fallback_topic(recent_topics: list[str], recent_tags: list[str], tag_counts: dict, daily_topics: set[str], topic_rotation: dict) -> Topic:
    """Seleciona tópico localmente sem chamar o Gemini."""
    return pick_topic(
        recent_topics=recent_topics,
        recent_tags=recent_tags,
        tag_counts=tag_counts,
        excluded_slugs=daily_topics,
        topic_rotation=topic_rotation,
    )


def _topic_from_trend_local(trend: str) -> Topic:
    """
    Converte uma trend em Topic usando apenas lógica local (sem Gemini).
    Mapeia keywords para tags conhecidas.
    """
    TAG_KEYWORDS: dict[str, list[str]] = {
        "sleep": ["sleep", "insomnia", "rest", "nap", "circadian"],
        "stress": ["stress", "anxiety", "burnout", "mindful", "meditat"],
        "gut": ["gut", "digest", "probiotic", "microbiome", "bloat"],
        "weight": ["weight", "fat", "metabol", "calorie", "bmi"],
        "recipes": ["recipe", "meal", "cook", "food", "diet", "eat", "protein"],
        "home-workouts": ["workout", "exercise", "fitness", "gym", "yoga", "walk", "strength"],
        "anti-inflammatory": ["inflam", "arthrit", "joint", "omega", "antioxidant"],
        "longevity": ["longevity", "aging", "lifespan", "centenar"],
        "mental-wellness": ["mental", "focus", "brain", "cognitive", "mood", "depress"],
        "healthy-habits": ["habit", "routine", "morning", "evening", "productivity"],
    }
    trend_lower = trend.lower()
    chosen_tag = "health"
    for tag, keywords in TAG_KEYWORDS.items():
        if any(kw in trend_lower for kw in keywords):
            chosen_tag = tag
            break

    slug = re.sub(r"[^a-z0-9]+", "-", trend_lower).strip("-")[:50]
    return Topic(
        slug=slug,
        name=trend.title(),
        angle="practical, science-backed tips for US readers",
        tag=chosen_tag,
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
    if not offers_path.exists():
        return None
    offers = json.loads(offers_path.read_text(encoding="utf-8"))
    compatible = [item for item in offers if topic_tag in item.get("tags", []) or "us" in item.get("tags", [])]
    return random.choice(compatible or offers) if offers else None


def _should_generate_today(posts_per_week: int) -> bool:
    if posts_per_week >= 7:
        return True
    return datetime.now(timezone.utc).weekday() < posts_per_week


def main() -> None:
    settings = load_settings()
    _setup_logging(settings.repo_root)

    if not _should_generate_today(settings.posts_per_week):
        LOG.info("Pulando geração hoje para manter %s posts/semana.", settings.posts_per_week)
        return

    today = datetime.now(timezone.utc).date()
    state_path = settings.repo_root / "generated" / "state.json"
    state = load_state(state_path)

    client = GeminiClient(api_keys=settings.gemini_api_keys, model=settings.gemini_model)
    checker = DuplicateChecker(index_path=settings.repo_root / "generated" / "content_index.json")

    # Tendências (404 não interrompe o pipeline)
    LOG.info("Buscando trending topics para USA...")
    try:
        trends = get_trending_topics()
        for trend in trends:
            _log_to_file(settings.repo_root, "trends.log", f"Found trend: {trend}")
    except Exception as exc:
        LOG.warning("Falha ao buscar trends (não fatal): %s", exc)
        trends = []

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
        LOG.info("═══ Slot %d/5 ═══", slot + 1)
        mode = _choose_mode(state)

        # ── Escolhe tópico (sem chamar Gemini) ───────────────────────────────
        topic: Topic | None = None
        for trend in list(trends):
            temp_slug = re.sub(r"[^a-z0-9]+", "-", trend.lower()).strip("-")[:50]
            if temp_slug not in recent_topics and temp_slug not in daily_topics:
                LOG.info("[Slot %d] Usando trending topic local: %s", slot + 1, trend)
                topic = _topic_from_trend_local(trend)
                trends.remove(trend)
                break

        if not topic:
            topic = _local_fallback_topic(recent_topics, recent_tags, tag_counts, daily_topics, topic_rotation)
            LOG.info("[Slot %d] Tópico local: %s (%s)", slot + 1, topic.name, topic.tag)

        offer = _pick_offer(settings.repo_root, topic.tag) if mode == "offer" else None

        # ── Hint de título local (sem chamar Gemini) ─────────────────────────
        title_hint = _local_title_hint(topic)
        LOG.info("[Slot %d] title_hint=%s", slot + 1, title_hint)

        try:
            # ── 1 chamada Gemini por artigo ───────────────────────────────────
            post: dict[str, Any] | None = None
            try:
                candidate = generate_article(client, topic, title_hint, mode, offer)
                candidate["tag"] = normalize_tag(candidate.get("tag", "")) or normalize_tag(topic.tag) or "health"

                if not _validate_quality(candidate, topic.name):
                    LOG.warning("[Slot %d] Qualidade insuficiente — artigo descartado", slot + 1)
                else:
                    status, score = checker.check_similarity(
                        candidate["title"], candidate["meta_description"], candidate["html"]
                    )
                    if status == "BLOCK":
                        _log_to_file(
                            settings.repo_root,
                            "duplicate_blocked.log",
                            f"BLOCKED: {candidate['title']} (score: {score})",
                        )
                        LOG.warning("[Slot %d] Artigo bloqueado por similaridade (score=%.2f)", slot + 1, score)
                    else:
                        post = candidate
                        checker.add_to_index(post["title"], post["slug"], post["meta_description"], post["html"])

            except ValueError as exc:
                # MAX_TOKENS ou campo obrigatório ausente — não tenta repair, descarta o slot
                LOG.error("[Slot %d] Geração falhou (não recuperável): %s", slot + 1, exc)
            except RuntimeError as exc:
                # Gemini esgotou todas as tentativas — não bloqueia os demais slots
                LOG.error("[Slot %d] Gemini indisponível: %s", slot + 1, exc)

            if not post:
                LOG.error("[Slot %d] Slot descartado.", slot + 1)
                continue

            # ── Internal linking ──────────────────────────────────────────────
            related_for_links = get_related_internal_links(post["html"], existing_posts, post["slug"])
            if related_for_links:
                links_html = "<h3>Recommended Reading</h3><ul>"
                for rel in related_for_links:
                    links_html += f"<li><a href='{rel['url']}'>{rel['title']}</a></li>"
                links_html += "</ul>"
                post["html"] += links_html

            if post["slug"] in set(recent_slugs[-40:]) or post["slug"] in daily_slugs:
                post["slug"] = f"{post['slug']}-{today.strftime('%m%d')}-{slot + 1}"

            # Hero pública: .jpeg (compatível com navegadores e Pinterest)
            hero_rel = f"assets/{today.isoformat()}_{post['slug']}.jpeg"
            actual_hero_path = fetch_hero_image(
                settings.pexels_api_key,
                post["image_query"],
                settings.repo_root / "docs" / hero_rel,
            )

            # Imagem Pinterest com overlay: .png local (não publicada diretamente)
            pin_rel = f"generated/pinterest/{today.isoformat()}_{post['slug']}.png"
            create_pinterest_image(
                settings.pexels_api_key,
                post["image_query"],
                post["pin_title"],
                settings.repo_root / pin_rel,
                source_image_path=actual_hero_path,
            )

            record = publish_post(
                docs_dir=settings.repo_root / "docs",
                base_url=settings.base_url,
                site_title=settings.site_title,
                post=post,
                hero_path_rel=hero_rel,
                run_date=today,
            )

            # Google Indexing
            post_url = f"{settings.base_url}/{record['url']}"
            if settings.google_indexing_json_path:
                LOG.info("[Slot %d] Submetendo ao Google Indexing: %s", slot + 1, post_url)
                index_new_post(settings.repo_root, settings.google_indexing_json_path, post_url)

            _log_to_file(settings.repo_root, "published_posts.log", f"Published: {record['url']} ({mode})")

            # Pinterest CSV: Media URL aponta para a hero .jpeg pública
            post_link = f"https://health-ptg.pages.dev/{record['url']}"
            write_draft_pack(
                out_dir=settings.repo_root / "generated" / "pinterest",
                run_date=today,
                pin_title=post["pin_title"],
                pin_description=post["pin_description"],
                link=post_link,
                image_path=hero_rel,          # hero pública .jpeg — não a imagem de generated/
                tag=post.get("tag", ""),
            )

            daily_slugs.add(post["slug"])
            daily_topics.add(topic.slug)
            published_count += 1
            recent_topics.append(topic.slug)
            recent_tags.append(post["tag"])
            recent_slugs.append(post["slug"])
            recent_titles.append(post["title"])
            tag_counts[post["tag"]] = int(tag_counts.get(post["tag"], 0)) + 1
            topic_rotation[topic.tag] = int(topic_rotation.get(topic.tag, 0)) + 1

            LOG.info("[Slot %d] ✓ Publicado: %s (%s)", slot + 1, record["url"], mode)

        except Exception:
            LOG.exception("[Slot %d] Erro inesperado no slot", slot + 1)

    state.update(
        {
            "runs": int(state.get("runs", 0)) + 1,
            "recent_topics": recent_topics[-50:],
            "recent_tags": recent_tags[-50:],
            "recent_slugs": recent_slugs[-100:],
            "recent_titles": recent_titles[-60:],
            "tag_counts": tag_counts,
            "topic_rotation": topic_rotation,
            "last_run": today.isoformat(),
        }
    )
    save_state(state_path, state)
    LOG.info("Run completo. Publicados %d/5 posts.", published_count)


if __name__ == "__main__":
    main()
