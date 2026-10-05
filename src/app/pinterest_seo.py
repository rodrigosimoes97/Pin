from __future__ import annotations

import hashlib
import logging
import re
from typing import Any

from .pinterest_performance import PinterestPerformanceTracker
from .topics import Topic

LOG = logging.getLogger(__name__)

SEARCH_INTENTS = [
    "how_to",
    "list",
    "checklist",
    "tips",
    "mistakes",
    "guide",
    "routine",
]

# Stopwords para extração de core phrase
STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "for", "with", "this",
    "that", "your", "from", "how", "to", "of", "in", "on", "at",
    "is", "it", "my", "me", "i", "you", "we", "be", "do", "get",
    "can", "more", "less", "what", "why", "when", "which", "make",
    "feel", "start", "try", "stop", "build", "help", "keep", "give",
    "about", "into", "their", "will", "our", "all", "so", "up", "may",
    "could", "should", "has", "have", "had", "was", "were", "are",
    "been", "being", "does", "did", "new", "find", "finds", "by",
}

# Prefixos/templates que indicam um pin_title gerado por fallback local (não do Gemini)
_GENERIC_TITLE_PREFIXES = [
    "build a better week with",
    "feel better faster:",
    "a simpler way to",
    "what to do this week:",
    "small changes, real results:",
    "your practical plan for",
    "the busy person's guide to",
    "how to actually master",
    "stop struggling with",
    "ready for a change?",
    "your 5-minute reset for",
    "better ",
]


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _trim_at_word_boundary(text: str, max_chars: int) -> str:
    normalized = _normalize_whitespace(text)
    if len(normalized) <= max_chars:
        return normalized
    trimmed = normalized[: max_chars + 1].rsplit(" ", 1)[0]
    return trimmed if trimmed else normalized[:max_chars].strip()


def _stable_hash_index(seed: str, size: int) -> int:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    hashed = int(digest[:8], 16)
    spread = sum(ord(ch) for ch in seed)
    return (hashed + spread) % max(size, 1)


def _is_generic_fallback_title(title: str) -> bool:
    """Verifica se o pin_title vem de um template de fallback local genérico."""
    low = title.lower().strip()
    return any(low.startswith(p) for p in _GENERIC_TITLE_PREFIXES)


def extract_core_topic_phrase(topic_name: str, title: str = "") -> str:
    """
    Extrai uma frase focal limpa de 2 a 4 palavras a partir do tópico e título.
    Prefere termos que formam uma frase de busca natural e completa.
    """
    # Palavras que não devem terminar uma frase de busca (conectivos, preposições)
    _BAD_ENDINGS = {
        "and", "or", "the", "a", "an", "of", "in", "on", "at", "for",
        "with", "to", "by", "as", "is", "are", "was", "that", "linked",
        "may", "can", "do", "from", "into", "after", "these", "this",
    }

    def _clean_words(text: str) -> list[str]:
        clean = re.sub(r"[^\w\s-]", "", text or "").strip()
        return [w for w in clean.split() if w.lower() not in STOPWORDS and len(w) >= 3]

    def _build_phrase(words: list[str], max_words: int = 4) -> str:
        phrase_words = words[:max_words]
        # Remove palavras ruins no final
        while phrase_words and phrase_words[-1].lower() in _BAD_ENDINGS:
            phrase_words = phrase_words[:-1]
        return " ".join(phrase_words).lower() if len(phrase_words) >= 2 else ""

    topic_words = _clean_words(topic_name)
    if len(topic_words) >= 2:
        phrase = _build_phrase(topic_words, max_words=4)
        if phrase:
            return phrase

    title_words = _clean_words(title)
    if len(title_words) >= 2:
        phrase = _build_phrase(title_words, max_words=4)
        if phrase:
            return phrase

    fallback = re.sub(r"[^\w\s-]", "", topic_name or "").strip()
    return fallback.lower() if fallback else "healthy habits"



def detect_search_intent(
    title: str,
    topic_name: str,
    tag: str,
    html: str = "",
    performance_tracker: PinterestPerformanceTracker | None = None,
) -> str:
    """
    Classifica automaticamente o search intent do Pin em:
    how_to, list, checklist, tips, mistakes, guide, routine

    Ordem de prioridade (do mais específico ao mais genérico):
    1. mistakes  – indicadores negativos/alertas
    2. how_to    – instruções diretas
    3. checklist – checklists / planos de ação
    4. routine   – rotinas / agendas
    5. tips      – dicas
    6. list      – listas numeradas
    7. guide     – guias completos
    """
    text_to_check = f"{title} {topic_name}".lower()

    # 1. Mistakes / alertas / problemas de saúde
    mistake_exact = [
        "mistake", "mistakes", "avoid", "wrong", "harm", "harming",
        "never", "threaten", "worsen", "hidden danger", "danger", "ruin",
        "toxic", "worst", "lies", "myth", "myths", "cancer", "disease",
        "linked to", "may hurt", "can harm", "hurting", "hurts",
        "worsens", "damage", "damages", "kill", "kills", "threat",
        "warning", "risky", "risks", "problematic",
    ]
    # Patterns adicionais que não usam \b (para strings compostas)
    mistake_compound = ["linked to", "may hurt", "can harm", "hidden danger", "may worsen"]
    if any(phrase in text_to_check for phrase in mistake_compound):
        return "mistakes"
    if any(re.search(rf"\b{re.escape(w)}\b", text_to_check) for w in mistake_exact):
        return "mistakes"

    # 2. How-To / passo a passo
    if re.search(r"\b(how to|how i|how you|ways? to|step by step|step-by-step)\b", text_to_check):
        return "how_to"

    # 3. Checklist / plano de ação
    checklist_patterns = ["checklist", "tracker", "action plan", "step-by-step", "habit tracker"]
    if any(phrase in text_to_check for phrase in checklist_patterns):
        return "checklist"
    if re.search(r"\bplan\b", text_to_check) and tag in {"healthy-habits", "home-workouts", "weight"}:
        return "checklist"

    # 4. Routine / agendas / schedules
    routine_phrases = ["routine", "schedule", "morning routine", "evening routine", "nightly routine",
                       "daily habit", "bedtime routine", "workout plan", "weekly plan"]
    if any(phrase in text_to_check for phrase in routine_phrases):
        return "routine"
    if tag in {"sleep", "home-workouts"} and re.search(r"\b(morning|evening|nightly|daily|bedtime|weekly)\b", text_to_check):
        return "routine"

    # 5. Tips / dicas
    tip_patterns = ["tips", "tip", "hacks", "tricks", "secrets", "advice", "quick wins"]
    if any(re.search(rf"\b{re.escape(w)}\b", text_to_check) for w in tip_patterns):
        return "tips"

    # 6. List (numerados / "foods / swaps / ideas")
    if re.search(r"\b\d+\b", text_to_check) or re.search(r"\b(reasons|foods|items|swaps|ideas|types|ways|signs)\b", text_to_check):
        return "list"

    # 7. Guide / guias completos
    guide_patterns = ["guide", "blueprint", "ultimate", "master", "deep dive", "overview",
                      "breakdown", "science", "research", "study", "review", "explained"]
    if any(re.search(rf"\b{re.escape(w)}\b", text_to_check) for w in guide_patterns):
        return "guide"

    # Consulta histórico de performance para tag
    if performance_tracker:
        historical_intent = performance_tracker.get_best_intent_for_tag(tag)
        if historical_intent and historical_intent in SEARCH_INTENTS:
            LOG.debug("[PinterestSEO] Usando intent histórico para tag '%s': %s", tag, historical_intent)
            return historical_intent

    # Fallback padrão por tag
    tag_defaults: dict[str, str] = {
        "recipes": "list",
        "home-workouts": "routine",
        "sleep": "routine",
        "stress": "tips",
        "gut": "tips",
        "weight": "guide",
        "anti-inflammatory": "list",
        "longevity": "guide",
        "mental-wellness": "tips",
        "healthy-habits": "checklist",
    }
    return tag_defaults.get(tag, "guide")


def generate_search_keywords(
    topic_name: str,
    title: str,
    tag: str,
    intent: str,
    primary_keyword: str,
) -> list[str]:
    """
    Gera de 5 a 8 frases de busca / long-tail keywords naturais em US English para o Pinterest.
    NÃO gera palavras isoladas soltas.
    Prioriza diversidade — evita repetir o mesmo core em todas as frases.
    """
    tag_clean = tag.replace("-", " ").strip()
    core = primary_keyword.strip() if primary_keyword else extract_core_topic_phrase(topic_name, title)

    # ── Grupo 1: frases contextuais por tag (sem usar core, mais naturais) ──
    tag_contextual_phrases: dict[str, list[str]] = {
        "recipes": [
            "healthy meal prep ideas",
            f"quick {tag_clean} recipes for beginners",
            "clean eating dinner ideas",
        ],
        "home-workouts": [
            "at home workout plan no equipment",
            "beginner home fitness routine",
            "quick daily exercise routine",
        ],
        "sleep": [
            "how to sleep better naturally",
            "bedtime routine for adults",
            "nighttime habits for deeper sleep",
        ],
        "stress": [
            "natural stress relief techniques",
            "how to lower cortisol naturally",
            "daily calm habits for anxiety",
        ],
        "gut": [
            "how to improve gut microbiome",
            "gut health foods for beginners",
            "bloating relief tips that work",
        ],
        "weight": [
            "sustainable weight loss habits",
            "realistic healthy weight tips",
            "how to lose weight without dieting",
        ],
        "anti-inflammatory": [
            "anti inflammatory foods list",
            "natural ways to reduce inflammation",
            "anti inflammatory meal plan ideas",
        ],
        "longevity": [
            "daily habits to live longer",
            "longevity lifestyle tips for adults",
            "healthy aging secrets that work",
        ],
        "mental-wellness": [
            "daily mental wellness habits",
            "how to improve mental clarity naturally",
            "mindset habits for stress relief",
        ],
        "healthy-habits": [
            "healthy daily routine for beginners",
            "simple wellness habits that stick",
            "easy healthy lifestyle changes",
        ],
    }

    # ── Grupo 2: frases baseadas no intent (usam core mas com prefixo variado) ──
    intent_phrase_templates: dict[str, list[str]] = {
        "how_to": [
            f"how to {core} step by step",
            f"easy ways to manage {core}",
            f"beginner guide to {core}",
            f"simple {core} tips for daily life",
        ],
        "list": [
            f"best {core} options to try",
            f"top foods for {core}",
            f"daily {tag_clean} ideas that work",
            f"simple {core} swaps for beginners",
        ],
        "checklist": [
            f"{core} checklist for beginners",
            f"daily {tag_clean} habit tracker",
            f"simple {core} action plan",
            f"healthy {tag_clean} checklist ideas",
        ],
        "tips": [
            f"practical {core} tips for everyday",
            f"science backed {tag_clean} advice",
            f"easy {core} hacks that actually work",
            f"top {tag_clean} tips for better health",
        ],
        "mistakes": [
            f"common {core} mistakes to avoid",
            f"{tag_clean} mistakes that hurt your health",
            f"hidden signs of bad {core}",
            f"what to avoid for better {tag_clean}",
        ],
        "guide": [
            f"complete {core} guide for beginners",
            f"practical {tag_clean} guide for busy people",
            f"everything about {core} explained",
            f"how {core} affects your health",
        ],
        "routine": [
            f"simple daily {core} routine",
            f"realistic {tag_clean} morning routine",
            f"easy {core} habit plan",
            f"daily {tag_clean} schedule for beginners",
        ],
    }

    candidates: list[str] = []

    # 1. Primary keyword (se tiver pelo menos 2 palavras)
    if core and len(core.split()) >= 2:
        candidates.append(core)

    # 2. Frases contextuais da tag (não repetem core diretamente)
    for phrase in tag_contextual_phrases.get(tag, [
        f"healthy {tag_clean} tips for beginners",
        f"simple {tag_clean} wellness guide",
        f"daily {tag_clean} habits that work",
    ]):
        clean_p = _normalize_whitespace(phrase.lower())
        if clean_p not in candidates and len(clean_p.split()) >= 2:
            candidates.append(clean_p)

    # 3. Frases do intent (usam core)
    for phrase in intent_phrase_templates.get(intent, intent_phrase_templates["guide"]):
        clean_p = _normalize_whitespace(phrase.lower())
        if clean_p not in candidates and len(clean_p.split()) >= 2:
            candidates.append(clean_p)

    # ── Filtro e normalização final ──
    final_keywords: list[str] = []
    for kw in candidates:
        kw_clean = re.sub(r"[^\w\s-]", "", kw).strip()
        word_count = len(kw_clean.split())
        if 2 <= word_count <= 7 and kw_clean not in final_keywords:
            final_keywords.append(kw_clean)
        if len(final_keywords) >= 8:
            break

    # Fallback se tiver menos de 5
    fallback_pool = [
        f"healthy {tag_clean} routine for beginners",
        f"daily {tag_clean} wellness tips",
        f"simple {tag_clean} guide",
        "wellness habits for real life",
        "easy healthy lifestyle tips",
    ]
    for fb in fallback_pool:
        if len(final_keywords) >= 5:
            break
        clean_fb = _normalize_whitespace(fb.lower())
        if clean_fb not in final_keywords:
            final_keywords.append(clean_fb)

    return final_keywords[:8]


def build_pinterest_title(
    title: str,
    topic_name: str,
    tag: str,
    intent: str,
    primary_keyword: str,
) -> str:
    """
    Gera um título otimizado para o Pinterest (40 a 70 caracteres).
    Preserva o título original se já for bom e não for um template genérico de fallback.
    """
    clean_title = _normalize_whitespace(title)

    # Usa título original se: tamanho certo E não é um fallback genérico
    if 40 <= len(clean_title) <= 70 and not _is_generic_fallback_title(clean_title):
        return clean_title

    core = _trim_at_word_boundary(
        primary_keyword.title() if primary_keyword else topic_name.title(), 38
    )
    tag_clean = tag.replace("-", " ").title()
    seed = f"{title}-{topic_name}-{intent}"

    intent_title_templates: dict[str, list[str]] = {
        "how_to": [
            "How to {core}: Simple Step-by-Step",
            "How to Master {core} in Real Life",
            "How to {core} Without the Stress",
            "A Realistic Way to {core} That Works",
        ],
        "list": [
            "Top {core} Ideas You Should Try",
            "The Best {core} for Better Health",
            "Key {core} Swaps That Make a Difference",
            "Essential {core} to Transform Your Day",
        ],
        "checklist": [
            "The Ultimate {core} Checklist",
            "Daily {core} Checklist for Beginners",
            "Your Simple {tag} Checklist: {core}",
            "The Quick {core} Action Plan",
        ],
        "tips": [
            "Practical {core} Tips That Actually Work",
            "Top {tag} Tips: {core} Made Easy",
            "Simple {core} Tips for Busy Days",
            "Science-Backed {core} Tips You Need",
        ],
        "mistakes": [
            "Common {core} Mistakes to Avoid",
            "Stop Making These {tag} Mistakes",
            "The Hidden {core} Mistake Hurting You",
            "Are You Making These {core} Errors?",
        ],
        "guide": [
            "The Busy Person's Guide to {core}",
            "Complete Guide: {core} Simplified",
            "Your Practical Blueprint for {core}",
            "Everything You Need to Know About {core}",
        ],
        "routine": [
            "A Simple {tag} Routine That Sticks",
            "Daily {core} Routine for Real Life",
            "The 5-Minute Reset for {core}",
            "Your Realistic {core} Daily Routine",
        ],
    }

    templates = intent_title_templates.get(intent, intent_title_templates["guide"])
    idx = _stable_hash_index(seed, len(templates))
    template = templates[idx]

    candidate = template.format(core=core, tag=tag_clean)
    candidate = _trim_at_word_boundary(candidate, 70)

    if len(candidate) < 40:
        candidate = f"{candidate} ({tag_clean} Guide)"
        candidate = _trim_at_word_boundary(candidate, 70)

    return candidate


def build_pinterest_description(
    title: str,
    meta_description: str,
    tag: str,
    intent: str,
    primary_keyword: str,
    html: str = "",
) -> str:
    """
    Gera uma descrição otimizada para o Pinterest (140 a 260 caracteres).
    Incorpora a primary keyword naturalmente e uma CTA alinhada ao intent.
    """
    tag_clean = tag.replace("-", " ")
    core = primary_keyword.lower() if primary_keyword else tag_clean

    intent_ctas: dict[str, str] = {
        "how_to": "Save this pin and follow these simple steps today.",
        "list": "Save this list and reference it every week.",
        "checklist": "Save this checklist and start your reset today.",
        "tips": "Save this for your daily wellness inspiration.",
        "mistakes": "Save this guide and stop making these common mistakes.",
        "guide": "Save this guide and read the full breakdown.",
        "routine": "Save this routine and make healthy habits stick.",
    }
    cta = intent_ctas.get(intent, "Save this pin for practical health tips.")

    intent_openings: dict[str, str] = {
        "how_to": f"Struggling to get results with {core}? Here is a clear, actionable breakdown you can follow on any schedule.",
        "list": f"Not sure what works for {core}? This curated list shows you exactly what to focus on for real, lasting results.",
        "checklist": f"Use this simple {core} checklist to stay on track without the overwhelm — built for real daily life.",
        "tips": f"Get science-backed {core} tips that actually fit your routine. No fluff, just practical steps that make a difference.",
        "mistakes": f"Most people make these {core} mistakes without realizing it. Here is what to avoid and what actually works.",
        "guide": f"Your no-nonsense guide to {core}. Practical steps, real answers, and zero generic advice — made for busy lives.",
        "routine": f"Build a consistent {core} routine that fits your real schedule. Start simple, stay consistent, see results.",
    }

    opening = intent_openings.get(intent, f"Discover practical {core} tips designed for everyday life and real schedules.")
    combined = _normalize_whitespace(f"{opening} {cta}")

    if len(combined) > 260:
        combined = _trim_at_word_boundary(combined, 260)
        if not combined.endswith((".", "!", "?")):
            combined = combined.rstrip() + "."

    if len(combined) < 140:
        supplement = f" Focused on {tag_clean} wellness with simple, manageable steps."
        combined = _normalize_whitespace(f"{opening}{supplement} {cta}")
        combined = _trim_at_word_boundary(combined, 260)

    return combined


def generate_pinterest_seo(
    topic: "Topic | str",
    article_data: dict[str, Any],
    performance_tracker: PinterestPerformanceTracker | None = None,
) -> dict[str, Any]:
    """
    Camada dedicada de Pinterest SEO — separada do SEO de artigo.

    Recebe: topic + article_data (saídos do Gemini/generate_article)
    Retorna:
    - intent         : "how_to" | "list" | "checklist" | "tips" | "mistakes" | "guide" | "routine"
    - primary_keyword: frase focal de 2-3 palavras (long-tail)
    - secondary_keywords: list[str] de frases de apoio
    - pin_title      : str 40-70 chars, otimizado Pinterest
    - pin_description: str 140-260 chars, otimizado Pinterest
    - keywords       : str CSV de 5-8 frases de busca (para o campo Keywords do Bulk Upload)
    - keywords_list  : list[str] das mesmas frases
    """
    from .topics import Topic as _Topic
    topic_name = topic.name if isinstance(topic, _Topic) else str(topic)
    topic_tag = topic.tag if isinstance(topic, _Topic) else ""
    tag = article_data.get("tag") or topic_tag or "health"
    title = article_data.get("title", "")
    html = article_data.get("html", "")
    meta_desc = article_data.get("meta_description", "")

    # ── 1. Search Intent ──────────────────────────────────────────────────────
    intent = detect_search_intent(
        title=title,
        topic_name=topic_name,
        tag=tag,
        html=html,
        performance_tracker=performance_tracker,
    )

    # ── 2. Primary Keyword ────────────────────────────────────────────────────
    primary_kw = extract_core_topic_phrase(topic_name, title)

    # ── 3. Long-tail Keywords (5–8 frases) ───────────────────────────────────
    keywords_list = generate_search_keywords(
        topic_name=topic_name,
        title=title,
        tag=tag,
        intent=intent,
        primary_keyword=primary_kw,
    )
    keywords_csv = ", ".join(keywords_list)
    secondary_kws = [kw for kw in keywords_list if kw != primary_kw][:4]

    # ── 4. Pin Title ──────────────────────────────────────────────────────────
    # Tenta preservar o título gerado pelo Gemini; só gera novo se for inválido ou genérico
    gemini_pin_title = _normalize_whitespace(article_data.get("pin_title", ""))
    if 40 <= len(gemini_pin_title) <= 70 and not _is_generic_fallback_title(gemini_pin_title):
        pin_title = gemini_pin_title
        LOG.debug("[PinterestSEO] Usando pin_title do Gemini: '%s'", pin_title)
    else:
        pin_title = build_pinterest_title(
            title=title,
            topic_name=topic_name,
            tag=tag,
            intent=intent,
            primary_keyword=primary_kw,
        )
        LOG.debug("[PinterestSEO] pin_title gerado localmente: '%s'", pin_title)

    # ── 5. Pin Description ────────────────────────────────────────────────────
    pin_description = build_pinterest_description(
        title=title,
        meta_description=meta_desc,
        tag=tag,
        intent=intent,
        primary_keyword=primary_kw,
        html=html,
    )

    seo_result = {
        "intent": intent,
        "primary_keyword": primary_kw,
        "secondary_keywords": secondary_kws,
        "pin_title": pin_title,
        "pin_description": pin_description,
        "keywords": keywords_csv,
        "keywords_list": keywords_list,
    }

    LOG.info(
        "[PinterestSEO] '%s' → Intent=%s | KW='%s' | Title='%s' (%d chars) | %d keywords",
        title[:35],
        intent,
        primary_kw,
        pin_title,
        len(pin_title),
        len(keywords_list),
    )

    return seo_result
