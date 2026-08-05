"""Odds movement enrichment — cross-book + temporal snapshot."""

from pathlib import Path

from hollersports.ml.features import extract_feature_vector
from hollersports.sources.odds_api import normalize_odds_api_events
from hollersports.sources.odds_movement import (
    apply_temporal_delta,
    enrich_markets_cross_book,
    enrich_markets_odds_movement,
    load_implied_snapshots,
    price_to_implied,
    save_implied_snapshots,
)


def test_price_to_implied_american_and_decimal():
    assert abs(price_to_implied(-110) - (110 / 210)) < 1e-9
    assert abs(price_to_implied(100) - 0.5) < 1e-9
    # decimal 2.0 → 0.5
    assert abs(price_to_implied(2.0) - 0.5) < 1e-9
    assert price_to_implied(0) is None


def test_cross_book_history_and_delta():
    markets = [
        {
            "event_id": "E1",
            "market_id": "E1:dk:h2h:HOME",
            "market_type": "MONEYLINE",
            "selection": "HOME",
            "price": 1.8,  # decimal ~0.555 implied
            "sportsbook": "draftkings",
        },
        {
            "event_id": "E1",
            "market_id": "E1:fd:h2h:HOME",
            "market_type": "MONEYLINE",
            "selection": "HOME",
            "price": 2.0,  # ~0.5
            "sportsbook": "fanduel",
        },
    ]
    out = enrich_markets_cross_book(markets)
    assert len(out) == 2
    for m in out:
        assert isinstance(m.get("odds_history"), list)
        assert len(m["odds_history"]) == 2
        assert m.get("book_dispersion") is not None
        assert m.get("odds_delta") is not None
    # Stable sportsbook order: draftkings then fanduel → delta = fd - dk
    imp_dk = 1.0 / 1.8
    imp_fd = 0.5
    assert abs(out[0]["odds_delta"] - (imp_fd - imp_dk)) < 1e-6


def test_temporal_snapshot_overrides_cross_book(tmp_path: Path):
    markets = [
        {
            "event_id": "E1",
            "market_id": "M1",
            "market_type": "MONEYLINE",
            "selection": "HOME_ML",
            "price": -150,
            "sportsbook": "consensus",
        }
    ]
    # First poll: write snapshot
    first = enrich_markets_odds_movement(
        markets, data_root=tmp_path, persist_snapshot=True
    )
    assert first[0].get("odds_delta") == 0.0 or first[0].get("odds_delta") is not None
    snaps = load_implied_snapshots(tmp_path)
    assert any("E1|MONEYLINE|HOME_ML" in k for k in snaps)

    # Second poll: price moved (more favorite)
    markets2 = [
        {
            "event_id": "E1",
            "market_id": "M1",
            "market_type": "MONEYLINE",
            "selection": "HOME_ML",
            "price": -200,
            "sportsbook": "consensus",
        }
    ]
    second = enrich_markets_odds_movement(
        markets2, data_root=tmp_path, persist_snapshot=True
    )
    assert second[0].get("odds_delta_source") == "temporal_snapshot"
    # -200 implied > -150 implied → positive delta
    assert second[0]["odds_delta"] > 0


def test_odds_api_normalize_attaches_cross_book():
    raw = [
        {
            "id": "evt1",
            "home_team": "Boston Celtics",
            "away_team": "Los Angeles Lakers",
            "commence_time": "2026-04-24T23:00:00Z",
            "bookmakers": [
                {
                    "key": "draftkings",
                    "markets": [
                        {
                            "key": "h2h",
                            "outcomes": [
                                {"name": "Boston Celtics", "price": -140},
                                {"name": "Los Angeles Lakers", "price": 120},
                            ],
                        }
                    ],
                },
                {
                    "key": "fanduel",
                    "markets": [
                        {
                            "key": "h2h",
                            "outcomes": [
                                {"name": "Boston Celtics", "price": -135},
                                {"name": "Los Angeles Lakers", "price": 115},
                            ],
                        }
                    ],
                },
            ],
        }
    ]
    events = normalize_odds_api_events(raw, league="NBA")
    ml = [m for m in events[0]["markets"] if m["market_type"] == "MONEYLINE"]
    assert all("odds_history" in m for m in ml)
    assert all(m.get("odds_delta") is not None for m in ml)
    # Features can consume odds_delta
    feat = extract_feature_vector(ml[0])
    assert feat is not None
    assert "odds_delta" in feat


def test_apply_temporal_delta_no_invent():
    markets = [{"event_id": "E", "market_type": "ML", "selection": "H", "price": -110}]
    # No prior → unchanged delta path
    out = apply_temporal_delta(markets, {})
    assert len(out) == 1
    assert "odds_delta_source" not in out[0]
