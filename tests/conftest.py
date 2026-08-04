"""Shared pytest fixtures and markers for HollerSports."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES_ROOT = REPO_ROOT / "fixtures"


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "unit: fast pure unit tests")
    config.addinivalue_line("markers", "integration: API / multi-module tests")
    config.addinivalue_line("markers", "golden: determinism / authority goldens")
    config.addinivalue_line(
        "markers", "calibration: advice-quality calibration ladder + model-edge gates"
    )


@pytest.fixture
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture
def fixtures_root() -> Path:
    return FIXTURES_ROOT


@pytest.fixture
def fixture_day001(fixtures_root: Path) -> Path:
    path = fixtures_root / "day001"
    assert path.is_dir(), f"missing fixture {path}"
    return path


@pytest.fixture
def fixture_day002(fixtures_root: Path) -> Path:
    path = fixtures_root / "day002"
    assert path.is_dir(), f"missing fixture {path}"
    return path


@pytest.fixture
def settled_sample_unreliable() -> list[dict]:
    """Below watch floor."""
    return [
        {"status": "WIN", "stake": 10.0, "pnl": 9.0, "strategy_id": "A"},
        {"status": "LOSS", "stake": 10.0, "pnl": -10.0, "strategy_id": "A"},
    ]


@pytest.fixture
def settled_sample_watch() -> list[dict]:
    """Watch band: enough sample for watch, not reliable floor (default 20)."""
    rows: list[dict] = []
    for i in range(8):
        rows.append(
            {
                "status": "WIN" if i % 2 == 0 else "LOSS",
                "stake": 10.0,
                "pnl": 9.0 if i % 2 == 0 else -10.0,
                "strategy_id": "MARKET_CONSENSUS_EDGE",
                "league": "NBA",
                "market_type": "ML",
            }
        )
    return rows


@pytest.fixture
def settled_sample_reliable() -> list[dict]:
    """Meets default reliable floors (n>=20, hit_rate>=0.45, sim_roi floor)."""
    rows: list[dict] = []
    # 12 wins, 8 losses → hit_rate 0.6; stakes 10; pnl ~ 12*9 + 8*(-10) = 28 → roi 0.14
    for i in range(20):
        win = i < 12
        rows.append(
            {
                "status": "WIN" if win else "LOSS",
                "stake": 10.0,
                "pnl": 9.0 if win else -10.0,
                "strategy_id": "MARKET_CONSENSUS_EDGE",
                "league": "NBA",
                "market_type": "ML",
            }
        )
    return rows
