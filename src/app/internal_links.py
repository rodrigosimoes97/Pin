from __future__ import annotations
import re
from typing import Any

def get_related_internal_links(post_content: str, all_posts: list[dict[str, Any]], current_slug: str, limit: int = 3) -> list[dict[str, Any]]:
    """
    Finds existing posts to link from the new post based on keyword overlap and tags.
    """
    if not all_posts:
        return []

    # Extract potential keywords from the new post content (simple approach)
    # Focus on words with more than 5 characters to avoid common stop words
    words = set(re.findall(r'\b\w{5,}\b', post_content.lower()))
    
    scored_posts = []
    for p in all_posts:
        if p.get("slug") == current_slug:
            continue
            
        score = 0
        title_lower = p.get("title", "").lower()
        desc_lower = p.get("description", "").lower()
        
        # Match title words
        title_words = set(re.findall(r'\b\w{5,}\b', title_lower))
        score += len(words.intersection(title_words)) * 3
        
        # Match description words
        desc_words = set(re.findall(r'\b\w{5,}\b', desc_lower))
        score += len(words.intersection(desc_words)) * 1
        
        if score > 0:
            scored_posts.append((score, p))
            
    # Sort by score descending
    scored_posts.sort(key=lambda x: x[0], reverse=True)
    
    # Extract only the post dictionary from the (score, post) tuple
    results = []
    for item in scored_posts[:limit]:
        if isinstance(item, tuple) and len(item) > 1:
            results.append(item[1])
        else:
            # Fallback if the structure is unexpected
            LOG.warning("Unexpected item structure in scored_posts: %s", type(item))
            
    return results
