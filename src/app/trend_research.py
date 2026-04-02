from __future__ import annotations

import logging
import re
from typing import Any

import requests
from bs4 import BeautifulSoup
from pytrends.request import TrendReq

LOG = logging.getLogger(__name__)

RSS_FEEDS = [
    "http://rss.cnn.com/rss/cnn_health.rss",
    "https://www.mayoclinic.org/rss/all-health-information-topics",
    "https://medicalxpress.com/rss-feed/health-news/",
]

REDDIT_URLS = [
    "https://www.reddit.com/r/health/top/.json?t=day&limit=10",
    "https://www.reddit.com/r/wellness/top/.json?t=day&limit=10",
    "https://www.reddit.com/r/fitness/top/.json?t=day&limit=10",
]

def get_trending_topics() -> list[str]:
    \"\"\"Fetches trending health topics from Google Trends, RSS, and Reddit.\"\"\"
    topics = []

    # 1. Fetch from Google Trends
    try:
        pytrends = TrendReq(hl='en-US', tz=360)
        trending_searches = pytrends.trending_searches(pn='united_states')
        for search in trending_searches[0][:15]:
            if _is_relevant(search):
                topics.append(search)
    except Exception as e:
        LOG.warning("Failed to fetch Google Trends: %s", e)

    # 2. Fetch from RSS
    for url in RSS_FEEDS:
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.content, "xml")
                items = soup.find_all("item")
                for item in items[:5]:
                    title = item.title.text if item.title else ""
                    if title:
                        topics.append(title)
        except Exception as e:
            LOG.warning("Failed to fetch RSS %s: %s", url, e)

    # 3. Fetch from Reddit
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
    for url in REDDIT_URLS:
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                children = data.get("data", {}).get("children", [])
                for child in children:
                    title = child.get("data", {}).get("title", "")
                    if title:
                        topics.append(title)
        except Exception as e:
            LOG.warning("Failed to fetch Reddit %s: %s", url, e)

    # Clean and filter
    cleaned_topics = []
    for t in topics:
        # Remove common non-health phrases or generic junk
        t = re.sub(r"\[.*?\]", "", t)
        t = t.strip()
        if len(t) > 10 and _is_relevant(t):
            cleaned_topics.append(t)

    # De-duplicate
    unique_topics = list(dict.fromkeys(cleaned_topics))
    return unique_topics[:10]

def _is_relevant(text: str) -> bool:
    \"\"\"Filters for health, fitness, and wellness only.\"\"\"
    keywords = [
        "health", "fitness", "wellness", "sleep", "diet", "nutrition", "exercise",
        "mental", "stress", "gut", "heart", "muscle", "brain", "body", "weight",
        "inflammation", "longevity", "aging", "workout", "recipe", "food",
        "blood sugar", "metabolic", "habit", "routine", "recovery", "pain",
        "immune", "doctor", "study", "research", "discovered", "benefit",
        "vitamin", "supplement", "mineral", "yoga", "meditation", "breathwork",
    ]
    text_lower = text.lower()
    return any(kw in text_lower for kw in keywords)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    trends = get_trending_topics()
    for i, trend in enumerate(trends, 1):
        print(f"{i}. {trend}")
