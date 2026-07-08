"""
Congress.gov API fetcher
Docs: https://api.congress.gov/
Free, no key required for basic use.
"""

import os
import requests
import logging


# Bill action text fragments that indicate a bill is still active/in-process.
# We include bills that have passed one chamber too — citizens should know.
ACTIVE_ACTION_KEYWORDS = [
    "introduced",
    "referred to",
    "committee",
    "reported",
    "passed house",
    "passed senate",
    "agreed to",
    "amendment",
    "cloture",
    "to president",
    "signed by president",  # just enacted — worth noting
    "became public law",    # just enacted
]

# Action text that means the bill is dead — skip these.
DEAD_ACTION_KEYWORDS = [
    "failed",
    "vetoed",
    "pocket vetoed",
    "indefinitely postponed",
    "tabled",
    "withdrawn",
]


class CongressFetcher:
    BASE_URL = "https://api.congress.gov/v3"

    def __init__(self, src_def: dict, locale: dict):
        self.src_def = src_def
        self.locale = locale
        self.api_key = src_def.get("api_key") or os.environ.get("CONGRESS_API_KEY", "")

    # 119th Congress started Jan 2025 — always fetch from current congress
    CURRENT_CONGRESS = 119

    def fetch(self) -> list:
        params = {
            "limit": 250,  # fetch more so we have enough after filtering placeholders
            "sort": "updateDate+desc",
            "format": "json",
        }
        if self.api_key:
            params["api_key"] = self.api_key

        try:
            url = f"{self.BASE_URL}/bill/{self.CURRENT_CONGRESS}"
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            bills = data.get("bills", [])
            active = [b for b in bills if self._is_active(b)]
            logging.info(f"Congress.gov: {len(bills)} fetched, {len(active)} active/in-process")
            return [self._normalize(b) for b in active]
        except Exception as e:
            logging.error(f"Congress.gov fetch failed: {e}")
            return []

    def _is_active(self, raw: dict) -> bool:
        # Skip placeholder bills
        title = (raw.get("title") or "").lower()
        if "reserved for the" in title:
            return False
        action_text = ((raw.get("latestAction") or {}).get("text") or "").lower()
        # Explicitly dead? Skip.
        if any(kw in action_text for kw in DEAD_ACTION_KEYWORDS):
            return False
        # Matches an active keyword? Include.
        if any(kw in action_text for kw in ACTIVE_ACTION_KEYWORDS):
            return True
        # No clear signal — include with a note (better to over-include than miss active bills)
        return True

    def _normalize(self, raw: dict) -> dict:
        latest_action = raw.get("latestAction") or {}
        bill_type = raw.get("type", "").lower()
        bill_num = raw.get("number", "")
        congress = raw.get("congress", "")
        url = raw.get("url") or f"https://www.congress.gov/bill/{congress}th-congress/{bill_type}/{bill_num}"
        return {
            "id": f"congress-{congress}-{raw.get('type')}-{bill_num}",
            "title": raw.get("title", "Untitled"),
            "summary": raw.get("title", ""),
            "full_text": None,
            "status": latest_action.get("text", "Status unknown"),
            "status_date": latest_action.get("actionDate", ""),
            "url": url,
            "source": "U.S. Congress",
            "tags": self.locale.get("tags", []),
        }
