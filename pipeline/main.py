#!/usr/bin/env python3
"""
Plain Law Pipeline
Fetches legislation from configured sources, summarizes via local Gemma model,
and pushes plain-language output to GitHub Pages.
"""

import os
import yaml
import logging
import argparse
from pathlib import Path
from datetime import datetime

from fetchers import get_fetcher
from summarizer import Summarizer
from publisher import Publisher
from dedup import DedupStore

BASE_DIR = Path(__file__).parent.parent
SOURCES_DIR = BASE_DIR / "sources"
CONFIG_PATH = BASE_DIR / "pipeline" / "config.yaml"


def load_config():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def load_sources():
    """Walk the sources/ directory and load all enabled source files."""
    sources = []
    for yaml_file in SOURCES_DIR.rglob("*.yaml"):
        if yaml_file.name.startswith("_"):
            continue  # skip schema/meta files
        with open(yaml_file) as f:
            source = yaml.safe_load(f)
        source["_file"] = str(yaml_file.relative_to(BASE_DIR))
        sources.append(source)
    return sources


def run(dry_run=False):
    config = load_config()
    sources = load_sources()
    dedup = DedupStore(config["pipeline"]["dedup_window_days"])
    summarizer = Summarizer(config["model"], config["pipeline"]["pipeline"]["prompt_template"] if "pipeline" in config else config["summarizer"]["prompt_template"])
    publisher = Publisher(config["output"])

    logging.info(f"Loaded {len(sources)} source files")

    results = []
    bill_count = 0

    for source in sources:
        for src_def in source.get("sources", []):
            if not src_def.get("enabled", False):
                continue

            fetcher = get_fetcher(src_def["type"], src_def, source)
            if not fetcher:
                logging.warning(f"No fetcher for type '{src_def['type']}' in {source['_file']}")
                continue

            bills = fetcher.fetch()
            logging.info(f"  {source['name']}: fetched {len(bills)} bills")

            for bill in bills:
                if bill_count >= config["pipeline"]["max_bills_per_run"]:
                    break
                if dedup.seen(bill["id"]):
                    continue

                summary = summarizer.summarize(bill)
                results.append({"source": source, "bill": bill, "summary": summary})
                dedup.mark(bill["id"])
                bill_count += 1

    logging.info(f"Summarized {len(results)} bills")

    if not dry_run:
        publisher.publish(results)
    else:
        for r in results:
            print(f"\n--- {r['bill']['title']} ---\n{r['summary']}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Print summaries without publishing")
    parser.add_argument("--log-level", default="info", choices=["debug", "info", "warning", "error"])
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s [%(levelname)s] %(message)s"
    )

    run(dry_run=args.dry_run)
