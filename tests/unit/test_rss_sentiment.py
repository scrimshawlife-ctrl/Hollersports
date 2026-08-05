"""RSS parse + lexicon match — no network."""

from hollersports.sources.http_cache import cached_get_text
from hollersports.sources.rss_sentiment import (
    aggregate_sentiment,
    enrich_markets_from_rss,
    match_items_to_market,
    parse_feed_items,
)

SAMPLE_RSS = """<?xml version="1.0"?>
<rss version="2.0"><channel>
<title>Sports</title>
<item>
  <title>Warriors ride hot winning momentum into playoffs</title>
  <description>Golden State Warriors look dominant at home</description>
  <link>https://example.com/1</link>
</item>
<item>
  <title>Suns injury report star questionable road underdog</title>
  <description>Phoenix Suns fading after injury concerns</description>
</item>
<item>
  <title>Unrelated tennis news</title>
  <description>Federer exhibition</description>
</item>
</channel></rss>
"""


def test_parse_rss_items():
    items = parse_feed_items(SAMPLE_RSS)
    assert len(items) == 3
    assert "Warriors" in items[0]["title"]


def test_parse_bad_xml_empty():
    assert parse_feed_items("not xml") == []
    assert parse_feed_items("") == []


def test_match_and_enrich():
    markets = [
        {
            "event_id": "NBA-20260426-GSW-PHX",
            "market_id": "NBA-20260426-GSW-PHX-ML-HOME",
            "selection": "HOME_ML",
            "price": -150,
            "teams": ["GSW", "PHX", "Warriors", "Suns"],
        },
        {
            "event_id": "NBA-OTHER",
            "market_id": "OTHER",
            "selection": "HOME_ML",
            "price": -110,
            "teams": ["BOS", "LAL"],
        },
    ]
    packet = enrich_markets_from_rss(
        markets,
        feed_xmls=[SAMPLE_RSS],
        fetch=False,
    )
    assert packet["item_count"] == 3
    assert packet["matched_markets"] >= 1
    assert packet["capital_authority"] is False
    scored = [m for m in packet["markets"] if m.get("rss_hit_count")]
    assert scored
    assert scored[0].get("sentiment_source") == "rss_lexicon"
    assert scored[0].get("sentiment_score") is not None


def test_explicit_sentiment_preserved():
    markets = [
        {
            "market_id": "M1",
            "event_id": "Warriors-home",
            "selection": "HOME",
            "teams": ["Warriors"],
            "sentiment_score": 0.9,
        }
    ]
    packet = enrich_markets_from_rss(markets, feed_xmls=[SAMPLE_RSS], fetch=False)
    m = packet["markets"][0]
    assert m["sentiment_score"] == 0.9


def test_cached_get_text_roundtrip(tmp_path, monkeypatch):
    calls = {"n": 0}

    def fake_urlopen(req, timeout=20.0):  # noqa: ARG001
        calls["n"] += 1

        class Resp:
            def read(self):
                return b"<rss><channel><item><title>Hi</title></item></channel></rss>"

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        return Resp()

    monkeypatch.setattr(
        "hollersports.sources.http_cache.urlopen",
        fake_urlopen,
    )
    t1 = cached_get_text(
        "https://example.com/feed.xml",
        cache_dir=tmp_path,
        ttl_seconds=3600,
    )
    t2 = cached_get_text(
        "https://example.com/feed.xml",
        cache_dir=tmp_path,
        ttl_seconds=3600,
    )
    assert "Hi" in t1
    assert t1 == t2
    assert calls["n"] == 1
