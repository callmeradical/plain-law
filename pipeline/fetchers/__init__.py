from .congress import CongressFetcher
from .legiscan import LegiScanFetcher
from .rss import RSSFetcher
from .scrape import ScrapeFetcher


def get_fetcher(source_type: str, src_def: dict, locale: dict):
    provider = src_def.get("provider", "")

    if source_type == "api":
        if provider == "legiscan":
            return LegiScanFetcher(src_def, locale)
        elif provider == "congress" or "congress.gov" in src_def.get("url", ""):
            return CongressFetcher(src_def, locale)
    elif source_type == "rss":
        return RSSFetcher(src_def, locale)
    elif source_type == "scrape":
        return ScrapeFetcher(src_def, locale)

    return None
