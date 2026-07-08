"""Basic HTML scraper fetcher."""

import logging
import hashlib

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    requests = None
    BeautifulSoup = None


class ScrapeFetcher:
    def __init__(self, src_def: dict, locale: dict):
        self.url = src_def["url"]
        self.selector = src_def.get("selector", "a")
        self.locale = locale

    def fetch(self) -> list:
        if not requests or not BeautifulSoup:
            logging.error("requests/beautifulsoup4 not installed")
            return []
        try:
            resp = requests.get(self.url, timeout=30, headers={"User-Agent": "plain-law-bot/1.0"})
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            elements = soup.select(self.selector)[:20]
            return [self._normalize(el) for el in elements]
        except Exception as e:
            logging.error(f"Scrape failed for {self.url}: {e}")
            return []

    def _normalize(self, el) -> dict:
        text = el.get_text(strip=True)
        url = el.get("href", self.url)
        uid = hashlib.md5(f"{url}{text}".encode()).hexdigest()
        return {
            "id": f"scrape-{uid}",
            "title": text[:200],
            "summary": text,
            "full_text": None,
            "status": "",
            "url": url,
            "source": self.locale.get("name", "Scraped"),
            "tags": self.locale.get("tags", []),
        }
