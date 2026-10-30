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

# Prefixos de descrições genéricas/templates antigos para descartar em favor do texto natural
_GENERIC_DESC_PREFIXES = [
    "most people make these",
    "your no-nonsense guide to",
    "not sure what works for",
    "build a consistent",
    "use this simple",
    "get science-backed",
    "struggling to get results with",
    "feeling overwhelmed lately",
    "having trouble making",
    "if you cannot seem to keep up with",
    "tired of generic advice about",
    "stop overcomplicating",
]

# Mapeamento de tags para pastas focadas no Pinterest (US audience)
US_PINTEREST_BOARDS: dict[str, str] = {
    "recipes": "Healthy Recipes & Meal Prep",
    "home-workouts": "Home Workouts & Fitness",
    "healthy-habits": "Daily Healthy Habits",
    "stress": "Stress Relief & Mindfulness",
    "gut": "Gut Health & Digestion",
    "sleep": "Better Sleep & Rest",
    "weight": "Healthy Weight Loss Tips",
    "anti-inflammatory": "Anti-Inflammatory Living",
    "mental-wellness": "Mental Wellness & Self Care",
    "longevity": "Healthy Aging & Longevity",
    "health": "Health & Wellness",
}


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


def _is_generic_fallback_description(desc: str) -> bool:
    """Verifica se a pin_description vem de um template antigo/genérico de fallback."""
    low = desc.lower().strip()
    return any(low.startswith(p) for p in _GENERIC_DESC_PREFIXES)


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


AUTHENTIC_US_PINTEREST_KEYWORDS: dict[str, list[str]] = {
    "recipes": [
        "healthy dinner ideas",
        "easy meal prep",
        "clean eating recipes",
        "high protein meals",
        "quick healthy recipes",
        "healthy lunch ideas",
    ],
    "gut": [
        "gut health tips",
        "gut healing foods",
        "bloating remedies",
        "digestive health",
        "healthy gut diet",
        "improve gut health",
    ],
    "anti-inflammatory": [
        "anti inflammatory diet",
        "foods that fight inflammation",
        "anti inflammatory recipes",
        "natural inflammation remedies",
        "joint health diet",
        "anti inflammatory meal plan",
    ],
    "sleep": [
        "how to sleep better naturally",
        "bedtime routine for adults",
        "natural sleep remedies",
        "deep sleep habits",
        "nighttime routine",
        "fall asleep fast",
    ],
    "stress": [
        "stress relief tips",
        "how to lower cortisol naturally",
        "nervous system regulation",
        "daily mindfulness habits",
        "anxiety relief techniques",
        "calm mind routine",
    ],
    "home-workouts": [
        "home workout routine",
        "no equipment workout",
        "daily stretching routine",
        "beginner workout at home",
        "quick morning workout",
        "mobility exercises",
    ],
    "healthy-habits": [
        "healthy daily routine",
        "simple wellness habits",
        "healthy lifestyle tips",
        "daily healthy habits",
        "wellness routine for women",
        "easy habit reset",
    ],
    "weight": [
        "sustainable weight loss habits",
        "realistic healthy weight tips",
        "healthy metabolism habits",
        "habits for weight loss",
        "clean eating for weight loss",
        "healthy body reset",
    ],
    "longevity": [
        "daily habits to live longer",
        "longevity lifestyle tips",
        "healthy aging secrets",
        "anti aging daily habits",
        "cellular health nutrition",
        "vitality daily routine",
    ],
    "mental-wellness": [
        "mental wellness habits",
        "daily self care routine",
        "improve mental clarity naturally",
        "brain health habits",
        "mindset habits for calm",
        "emotional wellness tips",
    ],
    "health": [
        "healthy lifestyle tips",
        "daily wellness inspiration",
        "natural health remedies",
        "simple healthy habits",
        "healthy living guide",
        "wellness daily reset",
    ],
}


def generate_search_keywords(
    topic_name: str,
    title: str,
    tag: str,
    intent: str,
    primary_keyword: str = "",
    article_keywords: str = "",
) -> list[str]:
    """
    Gera de 5 a 8 termos de busca autênticos em US English para o Pinterest.
    Prioriza termos naturais pesquisados por usuários reais nos EUA,
    sem 'keyword stuffing' e sem frases sintéticas gramaticalmente quebradas.
    """
    tag_clean = tag.replace("-", " ").strip().lower()
    core = (primary_keyword or "").strip().lower()
    if not core:
        core = extract_core_topic_phrase(topic_name, title)

    candidates: list[str] = []

    def _add_candidate(cand: str) -> None:
        c = re.sub(r"[^\w\s-]", "", cand).strip().lower()
        c = _normalize_whitespace(c)
        words = c.split()
        if 2 <= len(words) <= 5 and c not in candidates:
            candidates.append(c)

    # 1. Palavras-chave vindas do Gemini (se geradas)
    if article_keywords:
        for kw in article_keywords.split(","):
            _add_candidate(kw)

    # 2. Primary keyword (se for válida e natural, 2 a 4 palavras)
    if core and 2 <= len(core.split()) <= 4:
        _add_candidate(core)

    # 3. Termos autênticos curados do Pinterest US para o nicho/tag
    pool = AUTHENTIC_US_PINTEREST_KEYWORDS.get(tag, AUTHENTIC_US_PINTEREST_KEYWORDS["health"])
    for kw in pool:
        _add_candidate(kw)

    # 4. Termos baseados no intent com linguagem natural e fluida
    intent_keywords: dict[str, list[str]] = {
        "how_to": [
            f"how to improve {tag_clean}",
            f"beginner {tag_clean} guide",
            f"easy {tag_clean} tips",
        ],
        "list": [
            f"best {tag_clean} ideas",
            f"top {tag_clean} tips",
            f"simple {tag_clean} swaps",
        ],
        "checklist": [
            f"daily {tag_clean} checklist",
            f"{tag_clean} habit tracker",
            f"healthy {tag_clean} plan",
        ],
        "tips": [
            f"practical {tag_clean} tips",
            f"daily {tag_clean} advice",
            f"simple {tag_clean} habits",
        ],
        "mistakes": [
            f"common {tag_clean} mistakes to avoid",
            f"{tag_clean} habits to stop",
            f"what to avoid for {tag_clean}",
        ],
        "guide": [
            f"complete {tag_clean} guide for beginners",
            f"practical {tag_clean} guide",
            f"simple guide to {tag_clean}",
        ],
        "routine": [
            f"simple daily {tag_clean} routine",
            f"realistic {tag_clean} habits",
            f"daily {tag_clean} schedule",
        ],
    }
    for kw in intent_keywords.get(intent, intent_keywords["guide"]):
        _add_candidate(kw)

    # Garante mínimo de 5 e máximo de 8 termos
    fallback_pool = [
        f"healthy {tag_clean} routine for beginners",
        f"daily {tag_clean} wellness tips",
        f"simple {tag_clean} guide",
        "wellness habits for real life",
        "easy healthy lifestyle tips",
    ]
    for fb in fallback_pool:
        if len(candidates) >= 5:
            break
        _add_candidate(fb)

    return candidates[:8]


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
    Se for longo, corta na fronteira de palavras sem quebrar.
    """
    clean_title = _normalize_whitespace(title)

    # 1. Se já está entre 40 e 70 chars e não é genérico, preserva
    if 40 <= len(clean_title) <= 70 and not _is_generic_fallback_title(clean_title):
        return clean_title

    # 2. Se for ligeiramente mais longo que 70 chars, corta no limite de palavras
    if len(clean_title) > 70:
        trimmed = _trim_at_word_boundary(clean_title, 70)
        if 40 <= len(trimmed) <= 70 and not _is_generic_fallback_title(trimmed):
            return trimmed

    # 3. Fallback seguro se não houver título do modelo ou for genérico
    tag_clean = tag.replace("-", " ").title()
    core = _trim_at_word_boundary(
        primary_keyword.title() if primary_keyword else topic_name.title(), 35
    )
    seed = f"{title}-{topic_name}-{intent}"

    intent_title_templates: dict[str, list[str]] = {
        "how_to": [
            "How to Improve Your {tag} Step-by-Step",
            "A Realistic Way to Master {tag} That Works",
            "How to Build Better {tag} Without Stress",
        ],
        "list": [
            "The Best {tag} Ideas for Everyday Wellness",
            "Top Science-Backed {tag} Tips to Try",
            "Key {tag} Swaps That Make a Real Difference",
        ],
        "checklist": [
            "The Ultimate Daily {tag} Checklist",
            "A Simple {tag} Action Plan for Beginners",
            "Your Daily {tag} Reset: Simple Checklist",
        ],
        "tips": [
            "Practical {tag} Tips That Actually Work",
            "Science-Backed {tag} Tips for Busy Days",
            "Simple {tag} Habits for Better Health",
        ],
        "mistakes": [
            "Common {tag} Mistakes and How to Avoid Them",
            "Stop Making These Common {tag} Mistakes",
            "Hidden {tag} Mistakes That Hurt Your Health",
        ],
        "guide": [
            "The Complete Beginner's Guide to {tag}",
            "Everything You Need to Know About {tag}",
            "Your Practical Blueprint for Better {tag}",
        ],
        "routine": [
            "A Simple Daily {tag} Routine That Sticks",
            "Realistic {tag} Habits for Everyday Life",
            "The 5-Minute Daily Reset for {tag}",
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
    Gera uma descrição otimizada para o Pinterest (140 a 260 caracteres)
    usada como fallback quando a descrição original do Gemini não estiver disponível
    ou for um template genérico repetitivo.
    """
    tag_clean = tag.replace("-", " ").strip()
    clean_meta = _normalize_whitespace(meta_description)

    intent_ctas: dict[str, str] = {
        "how_to": "Save this pin to follow these simple steps today!",
        "list": "Save this pin to keep these ideas handy whenever you need them!",
        "checklist": "Save this checklist and start your daily reset today!",
        "tips": "Save this pin for your daily health inspiration!",
        "mistakes": "Save this pin and stop making these common mistakes!",
        "guide": "Save this pin and read the complete breakdown!",
        "routine": "Save this routine and make healthy habits stick!",
    }
    cta = intent_ctas.get(intent, "Save this pin for practical health tips!")

    # 1. Se meta_description for de bom tamanho (80 a 190 chars), combina com CTA natural
    if 80 <= len(clean_meta) <= 190:
        base = clean_meta.rstrip(".!?")
        combined = f"{base}. {cta}"
        if 140 <= len(combined) <= 260:
            return combined

    # 2. Construção fluida baseada em tag + intent (sem recorte de strings desconexas)
    intent_descriptions: dict[str, str] = {
        "how_to": f"Looking for simple, realistic ways to improve your {tag_clean}? Discover practical steps designed for real life and busy schedules. {cta}",
        "list": f"Explore the best science-backed {tag_clean} ideas to help you feel better every day. Simple, manageable tips with zero generic advice. {cta}",
        "checklist": f"Use this practical {tag_clean} action plan to stay on track without the overwhelm. Designed for real daily schedules. {cta}",
        "tips": f"Get science-backed {tag_clean} tips that actually fit your daily routine. Realistic steps that make a noticeable difference. {cta}",
        "mistakes": f"Are you making common {tag_clean} mistakes without realizing it? Discover what to avoid and what actually works for lasting results. {cta}",
        "guide": f"Your practical, no-nonsense guide to {tag_clean}. Real answers and actionable steps designed for everyday life. {cta}",
        "routine": f"Build a consistent {tag_clean} routine that fits your actual schedule. Start small, stay consistent, and see lasting progress. {cta}",
    }

    desc = intent_descriptions.get(
        intent,
        f"Discover practical, science-backed {tag_clean} tips designed for everyday life. Simple steps to feel your best without stress. {cta}",
    )
    desc = _normalize_whitespace(desc)
    if len(desc) > 260:
        desc = _trim_at_word_boundary(desc, 260)
        if not desc.endswith((".", "!", "?")):
            desc = desc.rstrip() + "."

    if len(desc) < 140:
        desc = _trim_at_word_boundary(f"{desc} Built for real daily schedules with simple steps.", 260)

    return desc


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
    - pin_title      : str 40-70 chars, otimizado Pinterest US
    - pin_description: str 140-260 chars, linguagem natural e persuasiva US
    - keywords       : str CSV de 5-8 termos autênticos do Pinterest US
    - keywords_list  : list[str] das mesmas frases
    - board          : str pasta recomendada para o Pin (US audience)
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

    # ── 3. Keywords Autênticas do Pinterest US (5–8 termos) ───────────────────
    keywords_list = generate_search_keywords(
        topic_name=topic_name,
        title=title,
        tag=tag,
        intent=intent,
        primary_keyword=primary_kw,
        article_keywords=article_data.get("pin_keywords", ""),
    )
    keywords_csv = ", ".join(keywords_list)
    secondary_kws = [kw for kw in keywords_list if kw != primary_kw][:4]

    # ── 4. Pin Title ──────────────────────────────────────────────────────────
    # Preserva o título do Gemini se válido (ou corta suavemente em 70 chars); fallback seguro
    gemini_pin_title = _normalize_whitespace(article_data.get("pin_title", ""))
    if 40 <= len(gemini_pin_title) <= 70 and not _is_generic_fallback_title(gemini_pin_title):
        pin_title = gemini_pin_title
        LOG.debug("[PinterestSEO] Usando pin_title do Gemini: '%s'", pin_title)
    else:
        pin_title = build_pinterest_title(
            title=gemini_pin_title or title,
            topic_name=topic_name,
            tag=tag,
            intent=intent,
            primary_keyword=primary_kw,
        )
        LOG.debug("[PinterestSEO] pin_title gerado/refinado: '%s'", pin_title)

    # ── 5. Pin Description ────────────────────────────────────────────────────
    # Prioridade máxima: descrição natural gerada pelo Gemini
    gemini_pin_desc = _normalize_whitespace(article_data.get("pin_description", ""))
    if 140 <= len(gemini_pin_desc) <= 260 and not _is_generic_fallback_description(gemini_pin_desc):
        pin_description = gemini_pin_desc
        LOG.debug("[PinterestSEO] Preservando pin_description natural do Gemini: '%s'", pin_description)
    else:
        pin_description = build_pinterest_description(
            title=title,
            meta_description=meta_desc,
            tag=tag,
            intent=intent,
            primary_keyword=primary_kw,
            html=html,
        )
        LOG.debug("[PinterestSEO] pin_description gerado/fallback: '%s'", pin_description)

    # ── 6. Board Segmentado para o Nicho (US Audience) ────────────────────────
    board = US_PINTEREST_BOARDS.get(tag, "Health & Wellness")

    seo_result = {
        "intent": intent,
        "primary_keyword": primary_kw,
        "secondary_keywords": secondary_kws,
        "pin_title": pin_title,
        "pin_description": pin_description,
        "keywords": keywords_csv,
        "keywords_list": keywords_list,
        "board": board,
    }

    LOG.info(
        "[PinterestSEO] '%s' → Intent=%s | Board='%s' | Title='%s' (%d chars) | %d keywords",
        title[:35],
        intent,
        board,
        pin_title,
        len(pin_title),
        len(keywords_list),
    )

    return seo_result
