from __future__ import annotations

import hashlib
import re
from typing import Any

from .gemini_client import GeminiClient
from .topics import Topic

ALLOWED_TAGS = {
    "sleep",
    "stress",
    "recipes",
    "home-workouts",
    "gut",
    "weight",
    "anti-inflammatory",
    "longevity",
    "mental-wellness",
    "healthy-habits",
    "health",
}

# ──────────────────────────────────────────────────────────────────────────────
# Prompt único: gera título + artigo completo em 1 chamada Gemini
# ──────────────────────────────────────────────────────────────────────────────
CONTENT_PROMPT = """\
Write a high-quality, deeply researched, evidence-informed health article for a discerning US audience.
Return a strict JSON object only (no markdown, no code fences) with EXACTLY these keys:
title, slug, meta_description, html, image_query, pin_title, pin_description, pin_keywords, alt_text, tag, faq

CRITICAL JSON RULES (read carefully before generating):
- NO literal newlines inside any JSON string value — use \\n instead.
- Escape all double-quote characters inside strings with \\".
- The entire response must be a single valid JSON object.
- Do NOT wrap in ```json or any markdown.

EDITORIAL & SCIENTIFIC INTEGRITY RULES:
- Write in authoritative, accessible, and engaging US health journalism English.
- Target US readers seeking realistic, sustainable health guidance.
- Ground all health claims in verifiable scientific evidence and guidance from respected institutions:
  prioritize NIH (National Institutes of Health), CDC (Centers for Disease Control and Prevention),
  FDA, peer-reviewed medical journals (e.g. JAMA, The Lancet, NEJM, BMJ, PubMed-indexed research),
  and accredited university medical centers.
- DO NOT invent fictitious personal anecdotes, fake first-person stories, or unverified claims.
  Do NOT use fabricated "I," "me," "my personal struggle" personas. Write with an evidence-informed,
  objective, and empathetic voice focusing on the reader ("you") and scientific consensus.
- NEVER invent studies, researchers, institutions, statistics, or quotes.
- Clearly differentiate between established clinical consensus, preliminary research (e.g. animal models or small cohorts), and emerging hypotheses.
- STRICTLY PROHIBITED: Never make promises of cures, diagnostic claims, or unsubstantiated medical advice.
- Minimum 550 words in the html body (excluding FAQ and metadata). Avoid superficial AI filler.

SEO & CONTENT STRUCTURE:
- Include {topic_name} naturally in: title, first paragraph, headings, and meta_description.
- Provide a clear, actionable angle: {angle}.

Input:
- topic_name: {topic_name}
- angle: {angle}
- title_hint: {title_hint}
- mode: {mode}
- offer_name: {offer_name}
- offer_link: {offer_link}

Allowed tag values (pick one, lowercase-hyphenated):
{allowed_tags}

Required HTML elements inside "html" field:
1. Myth-buster: <div class='myth-fact'><div class='myth-header'>Common Myth</div><div class='myth-body'>...</div><div class='fact-header'>Scientific Reality</div><div class='fact-body'>...</div></div>
2. Actionable Step: <div class='quick-win'><h3>Practical Daily Action</h3><p>...</p></div>
3. Expert Insight / Consensus Quote: <blockquote>...</blockquote>
4. Exactly 5 internal link placeholders:
   href="#recent-1" (anchor: related evidence-based guide)
   href="#recent-2" (anchor: practical wellness strategy)
   href="#recent-3" (anchor: daily habit guide)
   href="#recent-4" (anchor: consistent routine breakdown)
   href="#recent-5" (anchor: explore more [tag] articles)
5. Mandatory Scientific References Section at the end of the body:
   <section class='scientific-sources'><h2>Scientific References & Sources</h2><ul><li>...</li><li>...</li></ul></section>
   (Include at least 2-4 real citations or institutional references: NIH, CDC, FDA, or peer-reviewed journals).
6. Educational disclaimer sentence: "Educational and informational only — not medical advice."
7. If mode=offer: ethical recommendation + exact sentence "Disclosure: This page may contain affiliate links."
8. If mode=info: do NOT include affiliate links.

For "faq": array of 3-5 objects [{{"question":"...","answer":"..."}}]. Fact-based, concise answers.
For "title": clear, high-CTR, accurate SEO title (40–70 chars) based on title_hint. Avoid sensationalist clickbait.
For "slug": URL-friendly version of the title (lowercase, hyphens, max 80 chars, no extension).
For "meta_description": 140–160 chars, compelling, keyword-rich and evidence-focused.
For "image_query": 3–5 word natural Pexels search query (e.g. "fresh leafy vegetables kitchen", "sleep bedroom night").
For "pin_title": 40–70 chars, benefit-driven and clickable for US Pinterest audience.
For "pin_description": 150–250 chars. Engaging, natural US English highlighting actionable science-backed benefits, weaving in 2-3 search phrases with a clear CTA (e.g. "Save this for later!", "Read the full research-backed guide!").
For "pin_keywords": 4–6 authentic US search phrases (2–3 words each, comma-separated).
For "alt_text": accurate, descriptive image alt text (10–20 words).

If tag=recipes, include an additional key "recipe" with this exact shape:
{{
  "prep_time_minutes": 10,
  "cook_time_minutes": 20,
  "total_time_minutes": 30,
  "servings": "4 servings",
  "calories_per_serving": "220 calories",
  "ingredients": ["..."],
  "instructions": ["..."],
  "tips": ["..."],
  "storage": "..."
}}
"""


def normalize_tag(raw: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in (raw or ""))
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    cleaned = cleaned.strip("-")
    return cleaned if cleaned in ALLOWED_TAGS else ""


def generate_article(
    client: GeminiClient,
    topic: Topic,
    title_hint: str,
    mode: str,
    offer: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Gera artigo completo (incluindo título final) em uma única chamada Gemini.
    `title_hint` é uma sugestão de título; o modelo pode refiná-la.
    max_output_tokens aumentado para 4096 para evitar MAX_TOKENS em artigos com FAQ/recipe.
    """
    payload = client.generate_json(
        CONTENT_PROMPT.format(
            topic_name=topic.name,
            angle=topic.angle,
            title_hint=title_hint,
            mode=mode,
            offer_name=(offer or {}).get("name", ""),
            offer_link=(offer or {}).get("link", ""),
            allowed_tags=", ".join(sorted(ALLOWED_TAGS)),
        ),
        max_output_tokens=4096,
    )

    required = [
        "title",
        "slug",
        "meta_description",
        "html",
        "image_query",
        "pin_title",
        "pin_description",
        "alt_text",
    ]
    for key in required:
        if key not in payload or not isinstance(payload[key], str) or not payload[key].strip():
            raise ValueError(f"Campo obrigatório ausente ou inválido: {key}")

    cleaned_slug = _clean_slug(payload["slug"])
    final_tag = normalize_tag(str(payload.get("tag", ""))) or normalize_tag(topic.tag) or "health"
    payload["slug"] = cleaned_slug
    payload["tag"] = final_tag

    # pin_title e pin_description: usa os gerados pelo modelo se válidos, senão gera localmente
    pin_title = str(payload.get("pin_title", "")).strip()
    if not (40 <= len(pin_title) <= 70):
        pin_title = _build_pin_title(payload["title"], cleaned_slug, payload.get("meta_description", ""), final_tag)
    payload["pin_title"] = pin_title

    pin_desc = str(payload.get("pin_description", "")).strip()
    if not (140 <= len(pin_desc) <= 260):
        pin_desc = _build_pin_description(
            payload["title"],
            cleaned_slug,
            final_tag,
            payload.get("meta_description", ""),
            payload.get("html", ""),
        )
    payload["pin_description"] = pin_desc

    pin_kws = str(payload.get("pin_keywords", "")).strip()
    payload["pin_keywords"] = pin_kws

    if mode == "info":
        payload["html"] = payload["html"].replace("Disclosure: This page may contain affiliate links.", "")

    payload["faq"] = _normalize_faq(payload.get("faq"))
    payload["recipe"] = _normalize_recipe(payload.get("recipe"), payload["tag"])

    # Validação editorial prévia
    is_valid, reason = validate_article_quality(payload, topic.name)
    if not is_valid:
        raise ValueError(f"Artigo gerado rejeitado no controle editorial: {reason}")

    return payload


# ──────────────────────────────────────────────────────────────────────────────
# Validação Editorial e Científica
# ──────────────────────────────────────────────────────────────────────────────

FICTITIOUS_FIRST_PERSON_PATTERNS = [
    r"\bwhen I was diagnosed\b",
    r"\bin my personal experience\b",
    r"\bmy personal struggle\b",
    r"\bI personally struggled\b",
    r"\bI personally tried\b",
    r"\bas a former patient\b",
    r"\bmy personal journey with\b",
    r"\bI used to suffer from\b",
    r"\bmy doctor warned me personally\b",
]

FORBIDDEN_CURE_PATTERNS = [
    r"\bmiracle cure\b",
    r"\bguaranteed cure\b",
    r"\bcures (cancer|diabetes|alzheimer|dementia|hypertension|arthritis)\b",
    r"\bsecret cure\b",
    r"\binstant cure\b",
    r"\b100% cure\b",
    r"\bcure all diseases\b",
]

SCIENTIFIC_INDICATOR_KEYWORDS = [
    "study", "studies", "research", "researchers", "clinical", "trial",
    "nih", "cdc", "fda", "journal", "pubmed", "evidence", "review",
    "meta-analysis", "peer-reviewed", "investigators", "consensus",
]


def validate_article_quality(post: dict[str, Any], topic_name: str) -> tuple[bool, str]:
    """
    Validação editorial sênior:
    - Mínimo de 480 palavras de texto limpo
    - Presença do tópico no título ou corpo
    - Ausência de anedotas pessoais fictícias em 1ª pessoa
    - Ausência de promessas de cura milagrosas ou diagnósticos sem fundamentação
    - Presença comprovada de referências / linguagem baseada em evidências científicas
    - Variedade lexical contra superficialidade (TTR >= 0.35)
    - Pelo menos 2 perguntas no FAQ
    """
    if not isinstance(post, dict):
        return False, "Payload não é um dicionário válido"

    html = str(post.get("html", "")).strip()
    title = str(post.get("title", "")).strip()

    if not title:
        return False, "Título do artigo ausente"

    # 1. Contagem de palavras do corpo
    clean_text = re.sub(r"<[^>]+>", " ", html)
    clean_text = re.sub(r"\s+", " ", clean_text).strip()
    words = [w.lower() for w in re.findall(r"\b[a-zA-Z]{2,}\b", clean_text)]
    word_count = len(words)

    if word_count < 480:
        return False, f"Artigo muito superficial: {word_count} palavras (mínimo exigido: 480)"

    # 2. Presença do tópico no título ou corpo
    t_tokens = [t.lower() for t in re.findall(r"\b[a-zA-Z]{3,}\b", topic_name)]
    lower_title = title.lower()
    lower_body = clean_text.lower()
    found_topic = any(tok in lower_title or tok in lower_body for tok in t_tokens)

    if not found_topic and topic_name.lower() not in lower_title and topic_name.lower() not in lower_body:
        return False, f"Tópico focal '{topic_name}' ausente no título e corpo"

    # 3. Ausência de relatos pessoais autobiográficos fictícios
    for pattern in FICTITIOUS_FIRST_PERSON_PATTERNS:
        if re.search(pattern, clean_text, flags=re.IGNORECASE):
            return False, f"Artigo contém relato pessoal fictício em 1ª pessoa proibido: '{pattern}'"

    # 4. Ausência de promessas de cura proibidas
    for pattern in FORBIDDEN_CURE_PATTERNS:
        if re.search(pattern, clean_text, flags=re.IGNORECASE):
            return False, f"Artigo contém alegação ou promessa de cura perigosa proibida: '{pattern}'"

    # 5. Presença de embasamento científico
    found_science_markers = sum(1 for kw in SCIENTIFIC_INDICATOR_KEYWORDS if kw in words)
    if found_science_markers < 3:
        return False, f"Artigo sem embasamento científico suficiente (apenas {found_science_markers} menções científicas encontradas)"

    # 6. Variedade lexical (Type-Token Ratio para palavras >= 4 letras)
    meaningful_words = [w for w in words if len(w) >= 4]
    if meaningful_words:
        unique_ratio = len(set(meaningful_words)) / len(meaningful_words)
        if unique_ratio < 0.35:
            return False, f"Artigo superficial com vocabulário repetitivo (variedade lexical: {unique_ratio:.2f} < 0.35)"

    # 7. FAQs
    faq = post.get("faq")
    if not isinstance(faq, list) or len(faq) < 2:
        return False, "Artigo deve conter FAQ estruturada com pelo menos 2 perguntas"

    return True, ""


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _normalize_faq(raw: Any) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        return []
    items: list[dict[str, str]] = []
    for item in raw[:8]:
        if not isinstance(item, dict):
            continue
        question = str(item.get("question", "")).strip()
        answer = str(item.get("answer", "")).strip()
        if question and answer:
            items.append({"question": question, "answer": answer})
    return items


def _clean_slug(raw: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in raw)
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned.strip("-")[:80]


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _trim_at_word_boundary(text: str, max_chars: int) -> str:
    normalized = _normalize_whitespace(text)
    if len(normalized) <= max_chars:
        return normalized
    trimmed = normalized[: max_chars + 1].rsplit(" ", 1)[0]
    return trimmed if trimmed else normalized[:max_chars].strip()


def _stable_template_index(seed: str, size: int) -> int:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    hashed = int(digest[:8], 16)
    spread = sum(ord(ch) for ch in seed)
    return (hashed + spread) % size


def _extract_first_sentence(html: str) -> str:
    plain = re.sub(r"<[^>]+>", " ", html or "")
    plain = _normalize_whitespace(plain)
    if not plain:
        return ""
    first = re.split(r"(?<=[.!?])\s", plain, maxsplit=1)[0]
    return _trim_at_word_boundary(first, 100)


def _build_pin_title(title: str, slug: str, meta_description: str, tag: str) -> str:
    normalized_title = _normalize_whitespace(title)
    if 40 <= len(normalized_title) <= 70:
        return normalized_title

    keyword = _trim_at_word_boundary(normalized_title, 38)
    benefit_hint = _trim_at_word_boundary(meta_description or f"easy {tag.replace('-', ' ')} plan", 32)
    templates = [
        "Feel Better Faster: {keyword}",
        "A Simpler Way to {keyword}",
        "Build a Better Week With {keyword}",
        "What to Do This Week: {keyword}",
        "Small Changes, Real Results: {keyword}",
        "Your Practical Plan for {keyword}",
        "The Busy Person's Guide to {keyword}",
        "How to Actually Master {keyword}",
        "Stop Struggling With {keyword}",
        "Better {tag} Starts Here: {keyword}",
        "Ready for a Change? {keyword}",
        "Your 5-Minute Reset for {keyword}",
    ]
    idx = _stable_template_index(slug or normalized_title, len(templates))
    candidate = templates[idx].format(keyword=keyword.lower(), tag=tag.replace("-", " "))
    if len(candidate) < 40:
        candidate = _normalize_whitespace(f"{candidate}: {benefit_hint}")
    return _trim_at_word_boundary(candidate, 70)


_DUP_WORD_RE = re.compile(r"\b(\w+)(\s+\1\b)+", re.IGNORECASE)
_LEADING_LABEL_RE = re.compile(r"^\s*(question|tip|guide)\s*:\s*", re.IGNORECASE)


def _cleanup_pin_description(text: str, cta: str) -> str:
    text = _normalize_whitespace(text)
    text = _LEADING_LABEL_RE.sub("", text).strip()

    lower = text.lower()
    pos = lower.find(" based on ")
    if pos != -1:
        text = text[:pos].rstrip()
        if not text.endswith((".", "?", "!")):
            text += "."

    while True:
        new = _DUP_WORD_RE.sub(r"\1", text)
        if new == text:
            break
        text = new

    text = text.replace("?.", "?").replace(".?", "?")
    text = re.sub(r"\.\.+", ".", text)
    text = re.sub(r"\?\?+", "?", text)
    text = re.sub(r"!!+", "!", text)

    cta_clean = cta.strip().rstrip(".!?")
    for variant in ["Save this", "Try this today", "Read the full guide"]:
        variant_clean = variant.strip().rstrip(".!?")
        text = re.sub(rf"\s*{re.escape(variant_clean)}[.!?]\s*$", "", text, flags=re.IGNORECASE).rstrip()

    if not text.endswith((".", "?", "!")):
        text += "."
    text = text.rstrip() + f" {cta_clean}."

    return _normalize_whitespace(text)


def _build_pin_description(title: str, slug: str, tag: str, meta_description: str, html: str) -> str:
    del title
    tag_phrase = tag.replace("-", " ")
    base_topic = _trim_at_word_boundary(_normalize_whitespace(meta_description).lower(), 54)
    if not base_topic:
        base_topic = _trim_at_word_boundary(f"your {tag_phrase} routine", 54)

    specificity = ["today", "this week", "a 5-minute reset", "a 3-step routine", "your next meal", "tomorrow morning", "this weekend", "starting now"]
    ctas = ["Save this", "Try this today", "Read the full guide", "Check the checklist", "Get the plan"]

    seed = slug or meta_description or tag

    templates = [
        "Feeling overwhelmed lately? This {specific} plan helps you simplify {topic} with practical steps you can stick to.",
        "Struggling to stay consistent with {tag}? Try this {specific} approach to make progress without changing everything at once.",
        "Having trouble making {topic} work in real life? Use this {specific} framework to keep things simple and doable.",
        "If you cannot seem to keep up with {tag}, this breakdown focuses on realistic actions for busy days {specific}.",
        "When routines feel hard to maintain, {topic} usually needs a simpler plan. Start with this {specific} path and build momentum.",
        "Looking for a practical reset? This {specific} strategy helps you improve {tag} habits with clear, manageable steps.",
        "Stop overcomplicating {tag}. This {specific} guide shows you exactly how to focus on what matters most for {topic}.",
        "Want better results with less stress? This {specific} routine for {tag} is designed for real life, not a lab.",
        "Tired of generic advice about {tag}? This {specific} breakdown of {topic} gives you tools you can use immediately.",
    ]

    idx = _stable_template_index(seed, len(templates))
    specific = specificity[_stable_template_index(f"{seed}-specific", len(specificity))]
    cta = ctas[_stable_template_index(f"{seed}-cta", len(ctas))]

    template_text = templates[idx].format(topic=base_topic, tag=tag_phrase, specific=specific, cta=cta)
    description = _cleanup_pin_description(template_text, cta)
    description = _trim_at_word_boundary(description, 260)

    if len(description) < 140:
        extra = "Built for real schedules with one small step at a time."
        cta_sentence = f" {cta.strip().rstrip('.!?')}."
        if description.endswith(cta_sentence):
            base = description[: -len(cta_sentence)].rstrip()
            if not base.endswith((".", "?", "!")):
                base += "."
            description = _trim_at_word_boundary(f"{base} {extra} {cta.strip().rstrip('.!?')}.", 260)
        else:
            description = _trim_at_word_boundary(f"{description} {extra}", 260)

        description = _cleanup_pin_description(description, cta)
        description = _trim_at_word_boundary(description, 260)

    return description


def _normalize_recipe(raw: Any, tag: str) -> dict[str, Any] | None:
    if tag != "recipes":
        return None
    if not isinstance(raw, dict):
        raise ValueError("Missing or invalid recipe data for recipes tag")

    prep = _coerce_positive_int(raw.get("prep_time_minutes"), "prep_time_minutes")
    cook = _coerce_positive_int(raw.get("cook_time_minutes"), "cook_time_minutes")
    total = _coerce_positive_int(raw.get("total_time_minutes"), "total_time_minutes")
    servings = str(raw.get("servings", "")).strip()
    if not servings:
        raise ValueError("Missing or invalid recipe field: servings")

    calories = str(raw.get("calories_per_serving", "")).strip()
    ingredients = _normalize_recipe_list(raw.get("ingredients"), "ingredients", 25)
    instructions = _normalize_recipe_list(raw.get("instructions"), "instructions", 20)
    tips = _normalize_recipe_list(raw.get("tips"), "tips", 10, required=False)
    storage = str(raw.get("storage", "")).strip()

    if total < prep + cook:
        total = prep + cook

    return {
        "prep_time_minutes": prep,
        "cook_time_minutes": cook,
        "total_time_minutes": total,
        "servings": servings,
        "calories_per_serving": calories,
        "ingredients": ingredients,
        "instructions": instructions,
        "tips": tips,
        "storage": storage,
    }


def _normalize_recipe_list(raw: Any, field: str, limit: int, required: bool = True) -> list[str]:
    if raw is None:
        if required:
            raise ValueError(f"Missing or invalid recipe field: {field}")
        return []
    if not isinstance(raw, list):
        raise ValueError(f"Missing or invalid recipe field: {field}")
    cleaned: list[str] = []
    for item in raw[:limit]:
        value = str(item).strip()
        if value:
            cleaned.append(value)
    if required and not cleaned:
        raise ValueError(f"Missing or invalid recipe field: {field}")
    return cleaned


def _coerce_positive_int(value: Any, field: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Missing or invalid recipe field: {field}") from exc
    if parsed <= 0:
        raise ValueError(f"Missing or invalid recipe field: {field}")
    return min(parsed, 24 * 60)
