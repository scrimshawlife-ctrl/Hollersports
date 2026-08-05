#!/usr/bin/env python3
"""Fetch/parse RSS and score with offline lexicon (advisory).

CI-safe: pass --xml-file. Live: --fetch (network).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "packages" / "hollersports"))

from hollersports.sources.rss_sentiment import (  # noqa: E402
    DEFAULT_RSS_FEEDS,
    enrich_markets_from_rss,
    parse_feed_items,
)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--xml-file",
        action="append",
        default=[],
        help="Injected RSS/Atom XML path (repeatable); CI path",
    )
    p.add_argument("--fetch", action="store_true", help="Opt-in live HTTPS fetch")
    p.add_argument(
        "--feeds",
        default=None,
        help="Comma-separated feed URLs (default ESPN day-one sports)",
    )
    p.add_argument(
        "--markets-json",
        default=None,
        help="Optional odds_records.json / markets list to enrich",
    )
    p.add_argument("--out", default="data/ml/rss_sentiment.last.json")
    p.add_argument("--cache-dir", default="data/http_cache")
    args = p.parse_args()

    xmls = []
    for path in args.xml_file:
        xmls.append(Path(path).read_text(encoding="utf-8"))

    markets: list[dict] = []
    if args.markets_json:
        raw = json.loads(Path(args.markets_json).read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            markets = [m for m in (raw.get("markets") or []) if isinstance(m, dict)]
        elif isinstance(raw, list):
            markets = [m for m in raw if isinstance(m, dict)]

    feeds = None
    if args.feeds:
        feeds = [u.strip() for u in args.feeds.split(",") if u.strip()]
    elif args.fetch:
        feeds = list(DEFAULT_RSS_FEEDS)

    if not markets:
        # Report raw items only
        from hollersports.sources.rss_sentiment import collect_feed_items

        items, errors = collect_feed_items(
            feed_urls=feeds,
            feed_xmls=xmls,
            cache_dir=args.cache_dir,
            fetch=bool(args.fetch),
        )
        out = {
            "schema_version": "HollerRssItems.v1",
            "item_count": len(items),
            "items": items[:50],
            "errors": errors,
            "capital_authority": False,
            "execution_authority": False,
        }
    else:
        out = enrich_markets_from_rss(
            markets,
            feed_urls=feeds,
            feed_xmls=xmls,
            cache_dir=args.cache_dir,
            fetch=bool(args.fetch),
        )

    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: out[k] for k in out if k != "markets" and k != "items"}, indent=2))
    print(f"written={path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
