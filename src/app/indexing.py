from __future__ import annotations

import logging
from pathlib import Path

LOG = logging.getLogger(__name__)


def index_new_post(repo_root: Path, service_account_info: str, url: str) -> bool:
    """
    Deprecated: Google Indexing API foi descontinuada para páginas de blog
    por violar as diretrizes do Google (desenhada apenas para JobPosting e BroadcastEvent).
    A indexação de páginas de blog agora é tratada nativamente via Sitemap XML e IndexNow.
    """
    LOG.debug("[Indexing] Google Indexing API descontinuada para blogs; ignorando: %s", url)
    return True
