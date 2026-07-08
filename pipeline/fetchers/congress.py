"""
Congress.gov API fetcher
Docs: https://api.congress.gov/
Free, no key required for basic use.
"""

import requests
import logging


class CongressFetcher:
    BASE_URL = "https://api.congress.gov/v3"

    def __init__(self, src_def: dict, locale: dict):
        self.src_def = src_def
        self.locale = locale
        self.api_key = src_def.get("api_key") or ""

    def fetch(self) -> list:
        params = {
            "limit": 20,
            "sort": "updateDate+desc",
            "format": "json",
        }
        if self.api_key:
            params["api_key"] = self.api_key

        try:
            resp = requests.get(f"{self.BASE_URL}/bill", params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            bills = data.get("bills", [])
            return [self._normalize(b) for b in bills]
        except Exception as e:
            logging.error(f"Congress.gov fetch failed: {e}")
            return []

    def _normalize(self, raw: dict) -> dict:
        return {
            "id": f"congress-{raw.get('congress')}-{raw.get('type')}-{raw.get('number')}",
            "title": raw.get("title", "Untitled"),
            "summary": raw.get("title", ""),  # full text fetched separately if needed
            "full_text": None,
            "status": raw.get("latestAction", {}).get("text", ""),
            "url": raw.get("url", ""),
            "source": "U.S. Congress",
            "tags": self.locale.get("tags", []),
        }
