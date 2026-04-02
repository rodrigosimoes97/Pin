from __future__ import annotations

import logging
import time
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

import requests
from google.oauth2 import service_account
from google.auth.transport.requests import Request as GoogleRequest

LOG = logging.getLogger(__name__)

class GoogleIndexer:
    def __init__(self, service_account_json_path: str):
        self.json_path = service_account_json_path
        self.scopes = ["https://www.googleapis.com/auth/indexing"]
        self.credentials = None
        if self.json_path and Path(self.json_path).exists():
            try:
                self.credentials = service_account.Credentials.from_service_account_file(
                    self.json_path, scopes=self.scopes
                )
            except Exception as e:
                LOG.error("Failed to load Google service account: %s", e)
        else:
            LOG.warning("Google service account JSON not found at %s. Indexing disabled.", self.json_path)

    def _get_access_token(self) -> str | None:
        if not self.credentials:
            return None
        try:
            if not self.credentials.valid:
                self.credentials.refresh(GoogleRequest())
            return self.credentials.token
        except Exception as e:
            LOG.error("Failed to refresh Google access token: %s", e)
            return None

    def _log_result(self, repo_root: Path, filename: str, message: str):
        log_dir = repo_root / "generated" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        with open(log_dir / filename, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now(timezone.utc).isoformat()} - {message}\n")

    def publish_url(self, repo_root: Path, url: str, max_retries: int = 3) -> bool:
        if not self.credentials:
            return False

        token = self._get_access_token()
        if not token:
            return False

        endpoint = "https://indexing.googleapis.com/v3/urlNotifications:publish"
        payload = {
            "url": url,
            "type": "URL_UPDATED"
        }
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        for attempt in range(max_retries):
            try:
                response = requests.post(endpoint, json=payload, headers=headers, timeout=10)
                if response.status_code == 200:
                    LOG.info("Successfully submitted URL to Google Indexing: %s", url)
                    self._log_result(repo_root, "indexing_success.log", f"SUCCESS: {url}")
                    return True
                else:
                    error_msg = f"HTTP {response.status_code}: {response.text}"
                    LOG.warning("Attempt %d: Failed to index %s: %s", attempt + 1, url, error_msg)
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt) # Exponential backoff
                    else:
                        self._log_result(repo_root, "indexing_errors.log", f"ERROR: {url} - {error_msg}")
            except Exception as e:
                LOG.warning("Attempt %d: Exception during indexing %s: %s", attempt + 1, url, e)
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    self._log_result(repo_root, "indexing_errors.log", f"EXCEPTION: {url} - {e}")
        
        return False

def index_new_post(repo_root: Path, json_path: str, url: str):
    indexer = GoogleIndexer(json_path)
    return indexer.publish_url(repo_root, url)
