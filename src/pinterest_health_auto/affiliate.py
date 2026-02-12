from __future__ import annotations

from urllib.parse import quote_plus

from .config import settings


class IHerbAffiliateLinker:
    def build_link(self, topic: str) -> str:
        query = quote_plus(topic)
        base = settings.iherb_affiliate_base_url.rstrip("/")
        code = settings.iherb_affiliate_code
        if code:
            return f"{base}/search?kw={query}&rcode={code}"
        return f"{base}/search?kw={query}"
