"""Optional RSS sentiment enrichment (advisory; network opt-in).

Parse Atom/RSS feeds with stdlib XML, score titles/summaries via the offline
lexicon, and attach scores to markets that match team/selection tokens.

Never invents feed text. Inject ``feed_xml`` for CI. Live fetch is opt-in and
cached under ``data/http_cache``.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse

from hollersports.ml.sentiment import score_text_sentiment
from hollersports.schemas.hashing import packet_hash

# Default public sports RSS sources (HTTPS only). Operators may override.
DEFAULT_RSS_FEEDS: tuple[str, ...] = (
    "https://www.espn.com/espn/rss/nba/news",
    "https://www.espn.com/espn/rss/nfl/news",
    "https://www.espn.com/espn/rss/mlb/news",
)

_TOKEN = re.compile(r"[a-z0-9']+")
_NS_STRIP = re.compile(r"\{[^}]+\}")


def _local(tag: str) -> str:
    return _NS_STRIP.sub("", tag)


def _text(el: ET.Element | None) -> str:
    if el is None:
        return ""
    return " ".join((el.text or "").split())


def parse_feed_items(xml_text: str) -> list[dict[str, Any]]:
    """Parse RSS 2.0 or Atom into [{title, summary, link, published}]."""
    if not xml_text or not str(xml_text).strip():
        return []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    items: list[dict[str, Any]] = []
    # RSS: channel/item
    for el in root.iter():
        if _local(el.tag).lower() != "item":
            continue
        title = ""
        desc = ""
        link = ""
        pub = ""
        for child in el:
            name = _local(child.tag).lower()
            if name == "title":
                title = _text(child)
            elif name in {"description", "summary"}:
                desc = _text(child)
            elif name == "link":
                link = _text(child) or (child.get("href") or "")
            elif name in {"pubdate", "published", "updated"}:
                pub = _text(child)
        if title or desc:
            items.append(
                {
                    "title": title,
                    "summary": desc,
                    "link": link,
                    "published": pub,
                    "text": f"{title}. {desc}".strip(),
                }
            )

    # Atom: entry
    if not items:
        for el in root.iter():
            if _local(el.tag).lower() != "entry":
                continue
            title = ""
            summary = ""
            link = ""
            pub = ""
            for child in el:
                name = _local(child.tag).lower()
                if name == "title":
                    title = _text(child)
                elif name in {"summary", "content"}:
                    summary = _text(child)
                elif name == "link":
                    link = child.get("href") or _text(child)
                elif name in {"published", "updated"}:
                    pub = _text(child)
            if title or summary:
                items.append(
                    {
                        "title": title,
                        "summary": summary,
                        "link": link,
                        "published": pub,
                        "text": f"{title}. {summary}".strip(),
                    }
                )
    return items


def _market_tokens(market: Mapping[str, Any]) -> set[str]:
    parts: list[str] = []
    for key in ("selection", "event_id", "home_team", "away_team", "teams"):
        val = market.get(key)
        if isinstance(val, list):
            parts.extend(str(x) for x in val)
        elif val is not None:
            parts.append(str(val))
    # event_id often TEAM1-TEAM2
    blob = " ".join(parts).lower().replace("_", " ").replace("-", " ")
    toks = set(_TOKEN.findall(blob))
    # drop ultra-common noise
    toks -= {"ml", "home", "away", "moneyline", "the", "vs", "at"}
    return toks


def match_items_to_market(
    market: Mapping[str, Any],
    items: Sequence[Mapping[str, Any]],
    *,
    min_token_hits: int = 1,
) -> list[dict[str, Any]]:
    """Return feed items whose text shares tokens with the market identity."""
    mtoks = _market_tokens(market)
    if not mtoks:
        return []
    hits: list[dict[str, Any]] = []
    for it in items:
        text = str(it.get("text") or it.get("title") or "").lower()
        itoks = set(_TOKEN.findall(text))
        overlap = mtoks & itoks
        if len(overlap) >= min_token_hits:
            row = dict(it)
            row["matched_tokens"] = sorted(overlap)
            row["sentiment"] = score_text_sentiment(str(it.get("text") or it.get("title")))
            hits.append(row)
    return hits


def aggregate_sentiment(hits: Sequence[Mapping[str, Any]]) -> float:
    """Mean lexicon score over matched items; 0.0 if none."""
    if not hits:
        return 0.0
    scores = []
    for h in hits:
        if "sentiment" in h:
            try:
                scores.append(float(h["sentiment"]))
            except (TypeError, ValueError):
                continue
        else:
            scores.append(score_text_sentiment(str(h.get("text") or "")))
    if not scores:
        return 0.0
    return max(-1.0, min(1.0, sum(scores) / len(scores)))


def fetch_feed_xml(
    url: str,
    *,
    cache_dir: str | Path = "data/http_cache",
    ttl_seconds: float = 600.0,
    timeout_s: float = 20.0,
) -> str:
    """Live GET of RSS/Atom XML (HTTPS preferred). Raises on hard failure."""
    from hollersports.sources.http_cache import cached_get_text

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError(f"unsupported_feed_scheme:{parsed.scheme}")
    return cached_get_text(
        url, cache_dir=cache_dir, ttl_seconds=ttl_seconds, timeout_s=timeout_s
    )


def collect_feed_items(
    *,
    feed_urls: Sequence[str] | None = None,
    feed_xmls: Sequence[str] | None = None,
    cache_dir: str | Path = "data/http_cache",
    fetch: bool = False,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Load items from injected XML and/or optional live URLs.

    ``fetch=False`` (default): only ``feed_xmls`` used — CI safe.
    """
    items: list[dict[str, Any]] = []
    errors: list[str] = []
    for xml in feed_xmls or []:
        items.extend(parse_feed_items(xml))
    if fetch:
        urls = list(feed_urls) if feed_urls is not None else list(DEFAULT_RSS_FEEDS)
        for url in urls:
            try:
                xml = fetch_feed_xml(url, cache_dir=cache_dir)
                parsed = parse_feed_items(xml)
                for it in parsed:
                    it.setdefault("feed_url", url)
                items.extend(parsed)
            except Exception as exc:  # noqa: BLE001 — PARTIAL observation
                errors.append(f"feed:{url}:{type(exc).__name__}:{exc}")
    return items, errors


def enrich_markets_from_rss(
    markets: Sequence[Mapping[str, Any]],
    *,
    feed_urls: Sequence[str] | None = None,
    feed_xmls: Sequence[str] | None = None,
    cache_dir: str | Path = "data/http_cache",
    fetch: bool = False,
    min_token_hits: int = 1,
) -> dict[str, Any]:
    """Attach RSS-derived sentiment to markets. Fail soft when no matches.

    Explicit ``sentiment_score`` on a market is preserved (not overwritten).
    """
    items, errors = collect_feed_items(
        feed_urls=feed_urls,
        feed_xmls=feed_xmls,
        cache_dir=cache_dir,
        fetch=fetch,
    )
    out_markets: list[dict[str, Any]] = []
    matched = 0
    for m in markets:
        if not isinstance(m, Mapping):
            continue
        row = dict(m)
        hits = match_items_to_market(row, items, min_token_hits=min_token_hits)
        if hits:
            matched += 1
            score = aggregate_sentiment(hits)
            if row.get("sentiment_score") is None:
                row["sentiment_score"] = score
            row["sentiment_source"] = "rss_lexicon"
            row["rss_hit_count"] = len(hits)
            row["rss_headlines"] = [str(h.get("title") or "")[:200] for h in hits[:5]]
            # Prefer first headline as market headline if missing
            if not row.get("headline") and hits[0].get("title"):
                row["headline"] = str(hits[0]["title"])[:240]
        out_markets.append(row)

    packet = {
        "schema_version": "HollerRssSentimentPacket.v1",
        "status": "COMPUTED" if items else ("PARTIAL" if errors else "EMPTY"),
        "item_count": len(items),
        "market_count": len(out_markets),
        "matched_markets": matched,
        "markets": out_markets,
        "errors": errors,
        "fetch": bool(fetch),
        "capital_authority": False,
        "execution_authority": False,
        "authority": "SHADOW_ONLY",
        "mode": "ADVISORY_ONLY",
        "note": "advisory_rss_sentiment_no_money",
    }
    packet["packet_hash"] = packet_hash(
        {
            "item_count": packet["item_count"],
            "matched_markets": matched,
            "errors": errors,
        }
    )
    return packet
