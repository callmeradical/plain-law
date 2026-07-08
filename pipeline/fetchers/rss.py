"""RSS feed fetcher."""

import logging

try:
    import feedparser
except ImportError:
    feedparser = None


class RSSFetcher:
    def __init__(self, src_def: dict, locale: dict):
        self.url = src_def["url"]
        self.locale = locale

    def fetch(self) -> list:
        if not feedparser:
            logging.error("feedparser not installed — pip install feedparser")
            return []
        try:
            feed = feedparser.parse(self.url)
            return [self._normalize(e) for e in feed.entries[:20]]
        except Exception as e:
            logging.error(f"RSS fetch failed for {self.url}: {e}")
            return []

    def _normalize(self, entry) -> dict:
        return {
            "id": f"rss-{entry.get('id') or entry.get('link', '')}",
            "title": entry.get("title", "Untitled"),
            "summary": entry.get("summary", ""),
            "full_text": None,
            "status": "",
            "url": entry.get("link", ""),
            "source": self.locale.get("name", "RSS"),
            "tags": self.locale.get("tags", []),
        }
