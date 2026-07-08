"""
Simple file-backed dedup store.
Tracks bill IDs we've already processed to avoid re-summarizing.
"""

import json
import logging
from pathlib import Path
from datetime import datetime, timedelta

STORE_PATH = Path(__file__).parent.parent / ".dedup_store.json"


class DedupStore:
    def __init__(self, window_days: int = 30):
        self.window = timedelta(days=window_days)
        self.store = self._load()

    def _load(self) -> dict:
        if STORE_PATH.exists():
            try:
                with open(STORE_PATH) as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save(self):
        with open(STORE_PATH, "w") as f:
            json.dump(self.store, f, indent=2)

    def seen(self, bill_id: str) -> bool:
        if bill_id not in self.store:
            return False
        seen_at = datetime.fromisoformat(self.store[bill_id])
        return datetime.utcnow() - seen_at < self.window

    def mark(self, bill_id: str):
        self.store[bill_id] = datetime.utcnow().isoformat()
        self._save()
