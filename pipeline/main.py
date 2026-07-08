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

    prompt_key = (
        config["pipeline"]["pipeline"]["prompt_template"]
        if "pipeline" in config.get("pipeline", {})
        else config["summarizer"]["prompt_template"]
    )
    summarizer = Summarizer(config["model"], prompt_key)
    publisher = Publisher(config["output"])

    logging.info(f"Loaded {len(sources)} source files")

    results = []  # kept for dry-run / logging
    bill_count = 0
    max_bills = config["pipeline"]["max_bills_per_run"]

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
                if bill_count >= max_bills:
                    logging.info(f"Reached max_bills_per_run ({max_bills}), stopping.")
                    break
                if dedup.seen(bill["id"]):
                    logging.debug(f"Skipping duplicate: {bill['id']}")
                    continue

                summary = summarizer.summarize(bill)
                result = {"source": source, "bill": bill, "summary": summary}

                if dry_run:
                    print(f"\n--- {bill['title']} ---\n{summary}\n")
                else:
                    # Stream: commit this bill immediately after summarisation
                    publisher.publish_one(result)

                results.append(result)
                dedup.mark(bill["id"])
                bill_count += 1

    logging.info(f"Summarized and published {bill_count} bills")


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
