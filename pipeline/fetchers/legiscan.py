"""
LegiScan API fetcher
Docs: https://legiscan.com/legiscan
Free tier available. Requires LEGISCAN_API_KEY env var.
"""

import os
import requests
import logging


class LegiScanFetcher:
    BASE_URL = "https://api.legiscan.com/"

    def __init__(self, src_def: dict, locale: dict):
        self.src_def = src_def
        self.locale = locale
        self.api_key = os.environ.get("LEGISCAN_API_KEY", "")
        self.state = locale.get("state", "")

    def fetch(self) -> list:
        if not self.api_key:
            logging.warning("LEGISCAN_API_KEY not set — skipping LegiScan fetch")
            return []

        try:
            resp = requests.get(self.BASE_URL, params={
                "key": self.api_key,
                "op": "getMasterList",
                "state": self.state,
            }, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            if data.get("status") != "OK":
                logging.error(f"LegiScan error: {data.get('alert', {}).get('message')}")
                return []

            master_list = data.get("masterlist", {})
            bills = [v for k, v in master_list.items() if k != "session"]
            return [self._normalize(b) for b in bills[:20]]
        except Exception as e:
            logging.error(f"LegiScan fetch failed: {e}")
            return []

    def _normalize(self, raw: dict) -> dict:
        return {
            "id": f"legiscan-{self.state}-{raw.get('bill_id')}",
            "title": raw.get("title", "Untitled"),
            "summary": raw.get("description", raw.get("title", "")),
            "full_text": None,
            "status": raw.get("last_action", ""),
            "url": raw.get("url", ""),
            "source": f"{self.state} Legislature (LegiScan)",
            "tags": self.locale.get("tags", []),
        }
