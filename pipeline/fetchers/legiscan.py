"""
LegiScan API fetcher
Docs: https://legiscan.com/legiscan
Free tier available. Requires LEGISCAN_API_KEY env var.
"""

import os
import requests
import logging


# LegiScan bill status codes:
# 1 = Introduced, 2 = Engrossed, 3 = Enrolled, 4 = Passed, 5 = Vetoed, 6 = Failed
# 7 = Override, 8 = Chaptered (enacted), 9 = Refer, 10 = Report Pass, 11 = Report DNP, 12 = Draft
# We want everything except Failed (6) and Vetoed (5)
ACTIVE_STATUSES = {1, 2, 3, 4, 7, 8, 9, 10, 12}  # exclude 5 (vetoed) and 6 (failed)


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
            all_bills = [v for k, v in master_list.items() if k != "session"]
            active = [b for b in all_bills if self._is_active(b)]
            logging.info(f"LegiScan {self.state}: {len(all_bills)} total, {len(active)} active/in-process")
            return [self._normalize(b) for b in active[:50]]
        except Exception as e:
            logging.error(f"LegiScan fetch failed: {e}")
            return []

    def _is_active(self, raw: dict) -> bool:
        status = raw.get("status", 0)
        return int(status) in ACTIVE_STATUSES

    def _normalize(self, raw: dict) -> dict:
        status_code = int(raw.get("status", 0))
        status_labels = {
            1: "Introduced", 2: "Engrossed", 3: "Enrolled", 4: "Passed",
            5: "Vetoed", 6: "Failed", 7: "Veto Override", 8: "Enacted",
            9: "Referred", 10: "Reported — Pass", 11: "Reported — Do Not Pass", 12: "Draft"
        }
        return {
            "id": f"legiscan-{self.state}-{raw.get('bill_id')}",
            "title": raw.get("title", "Untitled"),
            "summary": raw.get("description", raw.get("title", "")),
            "full_text": None,
            "status": status_labels.get(status_code, raw.get("last_action", "Unknown")),
            "status_date": raw.get("last_action_date", ""),
            "url": raw.get("url", ""),
            "source": f"{self.state} Legislature (LegiScan)",
            "tags": self.locale.get("tags", []),
        }
