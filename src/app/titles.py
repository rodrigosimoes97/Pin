# src/app/titles.py
from __future__ import annotations

import re
from typing import List


TITLE_PROMPT = """
You are an SEO editor for US health & wellness content.

Generate EXACTLY 10 SEO-optimized blog post titles for this topic:
Topic: "{topic_name}"
Angle: "{angle}"

Rules:
- Use high-intent informational keywords (US search intent).
- Mix formats: questions, lists, guides, comparisons, bold benefit statements.
- Spark curiosity OR offer a practical solution.
- Avoid generic clichés like "The Ultimate Guide to…"
- Avoid clickbait lies and medical promises.
- Output MUST be strict JSON in this exact shape:
{{"titles":["Title 1","Title 2","Title 3","Title 4","Title 5","Title 6","Title 7","Title 8","Title 9","Title 10"]}}
No extra keys. No markdown. No commentary.
""".strip()


def _sanitize_titles(titles: List[str]) -> List[str]:
    cleaned = []
    for t in titles:
        t = (t or "").strip()
        # remove bullets/numbering if model sneaks it in
        t = re.sub(r"^\s*[\-\*\d\.\)\:]+\s*", "", t)
        if t:
            cleaned.append(t)
    # ensure exactly 10 if possible
    return cleaned[:10]


def generate_titles(client, topic, max_output_tokens: int = 700) -> List[str]:
    """
    Returns a list of 10 titles (strings).
    Expects client.generate_json(prompt, max_output_tokens=...) -> dict
    """
    prompt = TITLE_PROMPT.format(topic_name=topic.name, angle=topic.angle)
    payload = client.generate_json(prompt, max_output_tokens=max_output_tokens)

    titles = payload.get("titles")
    if not isinstance(titles, list) or len(titles) < 5:
        raise ValueError(f"Gemini returned invalid titles payload: {payload!r}")

    titles = _sanitize_titles([str(x) for x in titles])
    if len(titles) < 5:
        raise ValueError(f"Not enough usable titles after sanitization: {titles!r}")
    return titles


def pick_best_title(titles: List[str]) -> str:
    """
    Simple heuristic: prefer titles with a clear benefit + specificity.
    """
    if not titles:
        raise ValueError("No titles provided")
    # prefer question/list/comparison patterns often good for info intent
    preferred = []
    for t in titles:
        tl = t.lower()
        score = 0
        if "how to" in tl or tl.endswith("?"):
            score += 2
        if any(k in tl for k in ["best", "vs", "list", "tips", "foods", "exercises", "recipes", "habits", "routine"]):
            score += 1
        if any(k in tl for k in ["in 10 minutes", "without", "at home", "for beginners", "on a budget"]):
            score += 1
        preferred.append((score, t))
    preferred.sort(key=lambda x: x[0], reverse=True)
    return preferred[0][1]
