"""Offline lexicon sentiment — never invents text."""

from hollersports.ml.features import extract_feature_vector
from hollersports.ml.sentiment import (
    enrich_markets_sentiment,
    resolve_market_sentiment,
    score_text_sentiment,
)


def test_empty_text_zero():
    assert score_text_sentiment("") == 0.0
    assert score_text_sentiment(None) == 0.0
    assert resolve_market_sentiment({}) == 0.0


def test_lexicon_polarity():
    assert score_text_sentiment("hot winning momentum surge") > 0
    assert score_text_sentiment("injury slump questionable out") < 0


def test_explicit_score_preferred():
    assert resolve_market_sentiment({"sentiment_score": 0.5, "headline": "injury"}) == 0.5


def test_headline_feeds_features():
    feat = extract_feature_vector(
        {
            "selection": "HOME_ML",
            "price": -150,
            "headline": "dominant winning streak hot favorite",
        }
    )
    assert feat is not None
    assert feat["sentiment_score"] > 0


def test_enrich_sets_score_from_headline():
    out = enrich_markets_sentiment(
        [{"market_id": "M1", "headline": "cold slump losing streak"}]
    )
    assert out[0]["sentiment_score"] < 0
