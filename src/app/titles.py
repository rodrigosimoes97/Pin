from __future__ import annotations

import random

from .topics import Topic


# ──────────────────────────────────────────────────────────────────────────────
# Geração de título local (sem Gemini) — usado como hint para o artigo
# ──────────────────────────────────────────────────────────────────────────────

_TITLE_TEMPLATES = [
    "How to {verb} {topic} Without Giving Up Everything",
    "{count} Practical Ways to {verb} {topic} Starting Today",
    "Struggling with {topic}? Try This {adj} Reset",
    "Feel More Energized with This {adj} {topic} Routine",
    "The Honest Guide to {topic} for Busy People",
    "What Nobody Tells You About {topic}",
    "Stop Overcomplicating {topic} — Here's What Actually Works",
    "A Realistic {topic} Plan That Fits Your Real Life",
    "How I Finally Made {topic} Stick (And You Can Too)",
    "{count} Science-Backed {topic} Habits Worth Trying",
]

_VERBS = ["improve", "simplify", "build", "manage", "restart", "boost", "fix", "optimize"]
_ADJS = ["Simple", "Daily", "5-Minute", "Practical", "Effective", "Sustainable"]
_COUNTS = ["3", "5", "7", "4", "6"]


def _local_title_hint(topic: Topic) -> str:
    """
    Gera um hint de título localmente (sem Gemini).
    O modelo refinará isso no prompt unificado de artigo.
    """
    template = random.choice(_TITLE_TEMPLATES)
    title = template.format(
        topic=topic.name,
        verb=random.choice(_VERBS),
        adj=random.choice(_ADJS),
        count=random.choice(_COUNTS),
    )
    # Garante entre 40-80 chars para que seja um hint útil
    if len(title) > 80:
        title = title[:77].rsplit(" ", 1)[0] + "..."
    return title


# ──────────────────────────────────────────────────────────────────────────────
# Compatibilidade retroativa: generate_titles permanece disponível
# mas NÃO é mais chamado no pipeline principal (economiza 1 chamada Gemini/slot)
# ──────────────────────────────────────────────────────────────────────────────

TITLE_PROMPT = """You are an expert SEO editor for a major US health publication.
Return JSON only with schema: {{"titles": ["...", "..."]}}.
Create exactly 10 unique, high-CTR titles in US English for topic '{topic_name}' and angle '{angle}'.

Rules for High-Quality Titles:
- Use power words (e.g., Simple, Effective, Daily, Practical, Science-Backed, Realistic).
- Mix different formats:
  - The "How-To" (e.g., How to Actually [Benefit] Without [Struggle])
  - The "Listicle" (e.g., 5 Practical Ways to [Benefit] Today)
  - The "Question" (e.g., Struggling with [Topic]? Try This 5-Minute Reset)
  - The "Benefit-First" (e.g., Feel More Energized with This Simple [Topic] Routine)
- Target US search intent: informational, looking for quick wins and sustainable habits.
- avoid these phrases: Ultimate Guide, Best Ever, Secrets Revealed, You Won't Believe.
- each title must be between 40 and 70 characters.
- no numbering, no bullets, plain title text only.
"""


def generate_titles(
    client: object,  # GeminiClient — tipo fraco para evitar importação circular
    topic: Topic,
    excluded_titles: list[str] | None = None,
) -> list[str]:
    """
    Gera títulos via Gemini. Mantida para compatibilidade mas NÃO é chamada
    no pipeline principal — use _local_title_hint() + prompt unificado.
    """
    from .gemini_client import GeminiClient  # importação local para evitar circular

    assert isinstance(client, GeminiClient)

    excluded_text = ""
    if excluded_titles:
        excluded_text = f"\nAvoid these exact titles: {', '.join(excluded_titles[:10])}"

    payload = client.generate_json(
        TITLE_PROMPT.format(topic_name=topic.name, angle=topic.angle) + excluded_text,
        max_output_tokens=500,
    )
    titles = payload.get("titles", [])
    clean = []
    for title in titles:
        if not isinstance(title, str):
            continue
        t = " ".join(title.strip().split())
        if t and "ultimate guide" not in t.lower() and "best ever" not in t.lower():
            if not excluded_titles or t not in excluded_titles:
                clean.append(t)
    if len(clean) < 3:
        for title in titles:
            if isinstance(title, str) and title.strip():
                clean.append(title.strip())

    return clean[:10]


def pick_best_title(titles: list[str]) -> str:
    if not titles:
        return ""

    scored = []
    for t in titles:
        score = 0
        if "?" in t:
            score += 2
        for token in ["how", "what", "why", "tips", "foods", "routine", "guide", "checklist"]:
            if token in t.lower():
                score += 1
        score += random.uniform(0, 1.5)
        scored.append((score, t))

    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1]
