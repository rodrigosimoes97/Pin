from __future__ import annotations

import json
import logging
import os
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
from .pinterest_drafts import write_draft_pack, PINTEREST_BEST_HOURS_US
from .site import publish_post
from .state import load_state, save_state
from .titles import _local_title_hint
from .topics import pick_topic, Topic, PRIORITY_TAGS
from .duplicate_checker import DuplicateChecker
from .trend_research import get_trending_topics
from .internal_links import get_related_internal_links
from .indexing import index_new_post
from .pinterest_performance import PinterestPerformanceTracker
from .pinterest_seo import generate_pinterest_seo

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
    # Suprime logs excessivos de bibliotecas terceiras
    logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
    logging.getLogger("transformers").setLevel(logging.ERROR)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
    logging.getLogger("google").setLevel(logging.WARNING)
    logging.getLogger("google.auth").setLevel(logging.WARNING)
    logging.getLogger("googleapiclient").setLevel(logging.WARNING)


def _log_to_file(repo_root: Path, filename: str, message: str) -> None:
    log_dir = repo_root / "generated" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    with open(log_dir / filename, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now(timezone.utc).isoformat()} - {message}\n")


def _validate_quality(post: dict[str, Any], topic_name: str) -> tuple[bool, str]:
    """Verifica contagem de palavras e presença da keyword principal."""
    text = re.sub(r"<[^>]+>", " ", post.get("html", ""))
    word_count = len(text.split())

    if word_count < 450:
        return False, f"Artigo muito curto: {word_count} palavras geradas (mínimo exigido: 450)"

    topic_name_lower = topic_name.lower()
    if topic_name_lower not in post.get("title", "").lower() and topic_name_lower not in text.lower():
        return False, f"Tópico focal '{topic_name}' ausente no título e no corpo do texto"

    return True, ""


def _local_fallback_topic(
    recent_topics: list[str],
    recent_tags: list[str],
    tag_counts: dict,
    daily_topics: set[str],
    topic_rotation: dict,
) -> Topic:
    """Seleciona tópico localmente com base na rotação de tags e histórico."""
    return pick_topic(
        recent_topics=recent_topics,
        recent_tags=recent_tags,
        tag_counts=tag_counts,
        excluded_slugs=daily_topics,
        topic_rotation=topic_rotation,
    )


def _topic_from_trend_local(trend: str) -> Topic:
    """Converte uma trend em Topic mapeando keywords para tags conhecidas."""
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


def _write_execution_summary(
    today_str: str,
    target_posts: int,
    successful_posts: list[dict[str, Any]],
    failed_slots: list[dict[str, str]],
) -> None:
    """Gera resumo executivo detalhado no console e no GitHub Actions Step Summary."""
    banner = [
        "═══════════════════════════════════════════════════════════════",
        f"🚀 RESUMO DA EXECUÇÃO DIÁRIA — {today_str}",
        f"🎯 Meta Diária: {target_posts} post(s) | Publicados: {len(successful_posts)}/{target_posts}",
        "═══════════════════════════════════════════════════════════════",
    ]

    if successful_posts:
        banner.append("\n📝 POSTS E PINS CRIADOS COM SUCESSO:")
        for idx, item in enumerate(successful_posts, 1):
            banner.append(
                f"{idx}. \"{item['title']}\"\n"
                f"   • Board: {item['board']}\n"
                f"   • Tag: {item['tag']} | Intent: {item['intent']} | Horário: {item['publish_time']}\n"
                f"   • Keywords ({item['keywords_count']}): {item['keywords_preview']}\n"
                f"   • Link: {item['url']}"
            )
    else:
        banner.append("\n⚠️ Nenhum post publicado com sucesso nesta execução.")

    if failed_slots:
        banner.append("\n⚠️ OCORRÊNCIAS / TENTATIVAS QUE FALHARAM:")
        for fail in failed_slots:
            banner.append(f"• Tentativa #{fail['attempt']} (Tópico: '{fail['topic']}'): {fail['reason']}")

    banner.append("═══════════════════════════════════════════════════════════════")
    print("\n" + "\n".join(banner) + "\n")

    # Renderiza UI rica no GitHub Actions caso a variável exista
    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if summary_path:
        try:
            md_lines = [
                f"## 🚀 Resumo do Pipeline — {today_str}",
                "",
                f"- **Status da Meta:** `{len(successful_posts)}/{target_posts}` posts e pins gerados com sucesso",
                f"- **Meta Diária Configurada:** `{target_posts}` posts/dia",
                "",
            ]
            if successful_posts:
                md_lines.extend([
                    "### 📝 Posts e Pins Criados",
                    "| # | Título do Pin | Pasta (Board) | Tag | Horário (ET) | Keywords |",
                    "|:---:|:---|:---|:---:|:---:|:---:|",
                ])
                for idx, item in enumerate(successful_posts, 1):
                    md_lines.append(
                        f"| {idx} | [{item['title']}]({item['url']}) | `{item['board']}` | `{item['tag']}` | `{item['publish_time']}` | {item['keywords_count']} termos |"
                    )
                md_lines.append("")

            if failed_slots:
                md_lines.extend([
                    "### ⚠️ Ocorrências / Motivos de Descarte",
                    "| Tentativa | Tópico | Motivo |",
                    "|:---:|:---|:---|",
                ])
                for fail in failed_slots:
                    md_lines.append(f"| #{fail['attempt']} | {fail['topic']} | {fail['reason']} |")
                md_lines.append("")

            with open(summary_path, "a", encoding="utf-8") as f:
                f.write("\n".join(md_lines) + "\n")
        except Exception as exc:
            LOG.warning("Falha ao salvar GITHUB_STEP_SUMMARY: %s", exc)


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
    tracker = PinterestPerformanceTracker(storage_path=settings.repo_root / "generated" / "pinterest_performance.json")

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

    # Meta diária configurável (padrão: 3 posts por dia)
    target_posts = max(1, settings.posts_per_day)
    max_attempts = target_posts + 2  # permite até 2 tentativas extras caso algum artigo seja descartado

    successful_posts: list[dict[str, Any]] = []
    failed_slots: list[dict[str, str]] = []

    LOG.info(
        "═══ INICIANDO RUN DIÁRIO (Meta: %d posts/dia | Até %d tentativas) ═══",
        target_posts,
        max_attempts,
    )

    attempt = 0
    while published_count < target_posts and attempt < max_attempts:
        attempt += 1
        slot_label = f"Tentativa {attempt} (Post {published_count + 1}/{target_posts})"
        LOG.info("─── %s ───", slot_label)

        mode = _choose_mode(state)

        # ── Escolhe tópico (sem chamar Gemini) ───────────────────────────────
        topic: Topic | None = None
        for trend in list(trends):
            temp_slug = re.sub(r"[^a-z0-9]+", "-", trend.lower()).strip("-")[:50]
            if temp_slug not in recent_topics and temp_slug not in daily_topics:
                LOG.info("[%s] Usando trending topic: %s", slot_label, trend)
                topic = _topic_from_trend_local(trend)
                trends.remove(trend)
                break

        if not topic:
            topic = _local_fallback_topic(recent_topics, recent_tags, tag_counts, daily_topics, topic_rotation)
            LOG.info("[%s] Tópico selecionado: %s (tag: %s)", slot_label, topic.name, topic.tag)

        offer = _pick_offer(settings.repo_root, topic.tag) if mode == "offer" else None
        title_hint = _local_title_hint(topic)

        try:
            post: dict[str, Any] | None = None
            try:
                candidate = generate_article(client, topic, title_hint, mode, offer)
                candidate["tag"] = normalize_tag(candidate.get("tag", "")) or normalize_tag(topic.tag) or "health"

                is_valid, quality_msg = _validate_quality(candidate, topic.name)
                if not is_valid:
                    LOG.warning("[%s] Qualidade insuficiente: %s", slot_label, quality_msg)
                    failed_slots.append({"attempt": str(attempt), "topic": topic.name, "reason": quality_msg})
                else:
                    status, score = checker.check_similarity(
                        candidate["title"], candidate["meta_description"], candidate["html"]
                    )
                    if status == "BLOCK":
                        reason = f"Artigo descartado por similaridade excessiva com post anterior (sobreposição: {score:.1f}%)"
                        _log_to_file(
                            settings.repo_root,
                            "duplicate_blocked.log",
                            f"BLOCKED: {candidate['title']} (score: {score})",
                        )
                        LOG.warning("[%s] %s", slot_label, reason)
                        failed_slots.append({"attempt": str(attempt), "topic": topic.name, "reason": reason})
                    else:
                        post = candidate
                        checker.add_to_index(post["title"], post["slug"], post["meta_description"], post["html"])

            except ValueError as exc:
                reason = f"Erro no retorno estruturado do Gemini: {exc}"
                LOG.error("[%s] %s", slot_label, reason)
                failed_slots.append({"attempt": str(attempt), "topic": topic.name, "reason": reason})
            except RuntimeError as exc:
                reason = str(exc)
                LOG.error("[%s] %s", slot_label, reason)
                failed_slots.append({"attempt": str(attempt), "topic": topic.name, "reason": reason})
                # Se for cota esgotada (429), interrompe as tentativas restantes para não esperar em vão
                if "429" in reason or "cota" in reason.lower() or "limite" in reason.lower():
                    LOG.error("Interrompendo tentativas restantes devido a cota esgotada na API.")
                    break

            if not post:
                LOG.warning("[%s] Tentativa descartada sem publicação.", slot_label)
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
                post["slug"] = f"{post['slug']}-{today.strftime('%m%d')}-{published_count + 1}"

            # ── Camada de Pinterest SEO ───────────────────────────────────────
            pin_seo = generate_pinterest_seo(
                topic=topic,
                article_data=post,
                performance_tracker=tracker,
            )
            post["pin_title"] = pin_seo["pin_title"]
            post["pin_description"] = pin_seo["pin_description"]

            # Hero pública: .jpeg
            hero_rel = f"assets/{today.isoformat()}_{post['slug']}.jpeg"
            actual_hero_path = fetch_hero_image(
                settings.pexels_api_key,
                post["image_query"],
                settings.repo_root / "docs" / hero_rel,
            )

            # Imagem Pinterest com overlay: .png local
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
                index_new_post(settings.repo_root, settings.google_indexing_json_path, post_url)

            _log_to_file(settings.repo_root, "published_posts.log", f"Published: {record['url']} ({mode})")

            # Slot index baseado na ordem real dos posts publicados
            slot_idx = published_count
            time_idx = min(slot_idx, len(PINTEREST_BEST_HOURS_US) - 1)
            publish_hour_str = PINTEREST_BEST_HOURS_US[time_idx]

            post_link = f"https://health-ptg.pages.dev/{record['url']}"
            write_draft_pack(
                out_dir=settings.repo_root / "generated" / "pinterest",
                run_date=today,
                pin_title=post["pin_title"],
                pin_description=post["pin_description"],
                link=post_link,
                image_path=hero_rel,
                tag=post.get("tag", ""),
                slot_index=slot_idx,
                keywords=pin_seo["keywords"],
                intent=pin_seo["intent"],
                primary_keyword=pin_seo["primary_keyword"],
                board=pin_seo.get("board", ""),
            )

            # Registra no histórico de aprendizado do Pinterest
            tracker.record_pin(
                pin_date=today.isoformat(),
                url=post_link,
                topic=topic.name,
                tag=post["tag"],
                intent=pin_seo["intent"],
                primary_keyword=pin_seo["primary_keyword"],
                title=post["pin_title"],
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

            successful_posts.append({
                "title": post["pin_title"],
                "slug": post["slug"],
                "url": post_link,
                "tag": post["tag"],
                "board": pin_seo.get("board", "Health & Wellness"),
                "intent": pin_seo["intent"],
                "keywords_count": len(pin_seo["keywords_list"]),
                "keywords_preview": ", ".join(pin_seo["keywords_list"][:3]) + "...",
                "publish_time": publish_hour_str,
            })

            LOG.info(
                "[%s] ✓ Publicado com sucesso: '%s' | Board='%s'",
                slot_label,
                post["pin_title"],
                pin_seo.get("board"),
            )

        except Exception:
            LOG.exception("[%s] Erro inesperado na tentativa", slot_label)
            failed_slots.append({"attempt": str(attempt), "topic": topic.name if topic else "N/A", "reason": "Erro inesperado de execução"})

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

    # Exibe resumo detalhado
    _write_execution_summary(
        today_str=today.isoformat(),
        target_posts=target_posts,
        successful_posts=successful_posts,
        failed_slots=failed_slots,
    )


if __name__ == "__main__":
    main()
