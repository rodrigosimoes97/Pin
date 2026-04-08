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
    "https://www.sciencedaily.com/rss/health_medicine/nutrition.xml",
    "https://www.health.harvard.edu/blog/feed",
    "https://nutritionfacts.org/feed/",
]

REDDIT_URLS = [
    "https://www.reddit.com/r/health/top/.json?t=day&limit=15",
    "https://www.reddit.com/r/wellness/top/.json?t=day&limit=15",
    "https://www.reddit.com/r/fitness/top/.json?t=day&limit=15",
    "https://www.reddit.com/r/nutrition/top/.json?t=day&limit=15",
    "https://www.reddit.com/r/Biohackers/top/.json?t=day&limit=15",
]

def get_trending_topics() -> list[str]:
    """Fetches trending health topics from Google Trends, RSS, and Reddit."""
    topics = []

    # 1. Fetch from Google Trends
    try:
        # Use more modern endpoint for trending searches
        pytrends = TrendReq(hl='en-US', tz=360, timeout=(10, 25))
        # trending_searches is often 404, real_time_trending_searches is better but requires category
        # 1.1 Try real-time first (category 45 is Health)
        try:
            rt_trends = pytrends.real_time_trending_searches(pn='US', cat='m') # 'm' is Health in some versions
            for _, row in rt_trends.iterrows():
                title = row.get('title', '')
                if title and _is_relevant(title):
                    topics.append(title)
        except:
            # 1.2 Fallback to daily trending
            trending_searches = pytrends.trending_searches(pn='united_states')
            for search in trending_searches[0][:20]:
                if _is_relevant(search):
                    topics.append(search)
    except Exception as e:
        LOG.warning("Failed to fetch Google Trends (404/Error): %s. Moving to fallbacks.", e)

    # 2. Fetch from RSS (Backup)
    for url in RSS_FEEDS:
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            resp = requests.get(url, headers=headers, timeout=12)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.content, "xml")
                items = soup.find_all("item")
                for item in items[:8]:
                    title = item.title.text if item.title else ""
                    description = item.description.text if item.description else ""
                    # Check both title and description for relevance
                    if title and (_is_relevant(title) or _is_relevant(description)):
                        topics.append(title)
        except Exception as e:
            LOG.debug("Failed to fetch RSS %s: %s", url, e)

    # 3. Fetch from Reddit (Backup)
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
    for url in REDDIT_URLS:
        try:
            resp = requests.get(url, headers=headers, timeout=12)
            if resp.status_code == 200:
                data = resp.json()
                children = data.get("data", {}).get("children", [])
                for child in children:
                    t_data = child.get("data", {})
                    title = t_data.get("title", "")
                    selftext = t_data.get("selftext", "")
                    # Reddit titles can be clickbaity, check content too
                    if title and (_is_relevant(title) or _is_relevant(selftext)):
                        topics.append(title)
        except Exception as e:
            LOG.debug("Failed to fetch Reddit %s: %s", url, e)

    # Clean and filter
    cleaned_topics = []
    for t in topics:
        # Clean string
        t = re.sub(r"\[.*?\]", "", t) # Remove [Serious], [Video], etc
        t = re.sub(r"\(.*?\)", "", t)
        t = t.replace("\"", "").replace("'", "").strip()
        
        # Validation
        if len(t) > 15 and _is_relevant(t):
            cleaned_topics.append(t)

    # De-duplicate while preserving order
    seen = set()
    unique_topics = []
    for t in cleaned_topics:
        if t.lower() not in seen:
            seen.add(t.lower())
            unique_topics.append(t)
            
    LOG.info("Gathered %d unique trending topics.", len(unique_topics))
    return unique_topics[:15]

def _is_relevant(text: str) -> bool:
    """Filters for health, fitness, and nutrition only."""
    if not text: return False
    
    # Positive keywords (MUST have at least one)
    keywords = [
        "health", "fitness", "wellness", "sleep", "diet", "nutrition", "exercise",
        "mental", "stress", "gut", "heart", "muscle", "brain", "body", "weight",
        "inflammation", "longevity", "aging", "workout", "recipe", "food",
        "blood sugar", "metabolic", "habit", "routine", "recovery", "pain",
        "immune", "doctor", "study", "research", "discovered", "benefit",
        "vitamin", "supplement", "mineral", "yoga", "meditation", "breathwork",
        "cardio", "protein", "carbs", "fats", "fasting", "intermittent",
        "strength", "mobility", "flexibility", "joint", "back pain", "knees",
        "walking", "running", "hydration", "water", "coffee", "tea", "sugar",
        "organic", "probiotic", "prebiotic", "microbiome", "anxiety", "depression",
        "focus", "concentration", "energy", "fatigue", "tired", "insomnia",
    ]
    
    # Negative keywords (MUST NOT have any)
    exclude = [
        "crypto", "bitcoin", "stocks", "market", "politics", "war", "trump", "biden",
        "movie", "trailer", "gaming", "ps5", "xbox", "celebrity", "gossip", "actor",
        "actress", "tv show", "series", "football", "soccer", "basketball", "nba", "nfl",
        "hurricane", "earthquake", "shooting", "crime", "police", "court", "lawsuit",
    ]
    
    text_lower = text.lower()
    
    # First, check for exclusions
    if any(ex in text_lower for ex in exclude):
        return False
        
    # Then, check for relevance
    return any(kw in text_lower for kw in keywords)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    trends = get_trending_topics()
    for i, trend in enumerate(trends, 1):
        print(f"{i}. {trend}")
