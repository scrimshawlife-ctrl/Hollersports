#!/usr/bin/env python3
"""
Basic usage example for HollerSports engine with state management.

This demonstrates:
1. Initializing a slate with proper state isolation
2. Running the full pipeline
3. Exporting results with provenance
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.slate_runner import SlateRunner
from engine.reset_state import make_market_key
import json


def main():
    print("=" * 70)
    print("HollerSports Engine - Basic Usage Example")
    print("=" * 70)
    print()

    # Step 1: Define slate inputs
    print("Step 1: Defining slate inputs...")

    games_payload = {
        "games": [
            {
                "game_id": "NBA_20251217_LAL_BOS",
                "home_team": "BOS",
                "away_team": "LAL",
                "venue": "home",
                "start_time_utc": 1734469200,
            },
            {
                "game_id": "NBA_20251217_GSW_MIA",
                "home_team": "MIA",
                "away_team": "GSW",
                "venue": "home",
                "start_time_utc": 1734476400,
            },
        ]
    }

    # Define some example lines
    lines_payload = {}

    # LeBron James - Points
    key1 = make_market_key("NBA", "NBA_20251217_LAL_BOS", "player_123", "PTS", 25.5, "OVER")
    lines_payload[key1] = {
        "sport": "NBA",
        "game_id": "NBA_20251217_LAL_BOS",
        "player_id": "player_123",
        "player_name": "LeBron James",
        "market": "PTS",
        "line": 25.5,
    }

    # Jayson Tatum - Points
    key2 = make_market_key("NBA", "NBA_20251217_LAL_BOS", "player_124", "PTS", 28.5, "OVER")
    lines_payload[key2] = {
        "sport": "NBA",
        "game_id": "NBA_20251217_LAL_BOS",
        "player_id": "player_124",
        "player_name": "Jayson Tatum",
        "market": "PTS",
        "line": 28.5,
    }

    # Stephen Curry - Points + Assists
    key3 = make_market_key("NBA", "NBA_20251217_GSW_MIA", "player_456", "PRA", 35.5, "OVER")
    lines_payload[key3] = {
        "sport": "NBA",
        "game_id": "NBA_20251217_GSW_MIA",
        "player_id": "player_456",
        "player_name": "Stephen Curry",
        "market": "PRA",
        "line": 35.5,
    }

    # Jimmy Butler - Points
    key4 = make_market_key("NBA", "NBA_20251217_GSW_MIA", "player_457", "PTS", 22.5, "OVER")
    lines_payload[key4] = {
        "sport": "NBA",
        "game_id": "NBA_20251217_GSW_MIA",
        "player_id": "player_457",
        "player_name": "Jimmy Butler",
        "market": "PTS",
        "line": 22.5,
    }

    print(f"  - {len(games_payload['games'])} games defined")
    print(f"  - {len(lines_payload)} market lines defined")
    print()

    # Step 2: Initialize SlateRunner
    print("Step 2: Initializing SlateRunner...")

    runner = SlateRunner(
        slate_id="NBA_2025-12-17_EVENING",
        sport="NBA",
        provider="PrizePicks",
        games_payload=games_payload,
        lines_payload=lines_payload,
    )

    print(f"  - Slate ID: {runner.state.slate.slate_id}")
    print(f"  - Sport: {runner.state.slate.sport}")
    print(f"  - Provider: {runner.state.market.provider}")
    print(f"  - Source fingerprint: {runner.state.slate.source_fingerprint[:16]}...")
    print()

    # Step 3: Run full pipeline
    print("Step 3: Running full pipeline...")
    print("  (This will compute context, run simulations, and generate picks)")
    print()

    results = runner.run_full_pipeline(
        sim_iterations=10000,
        pick_strategy="edge",
        min_edge=0.05,
    )

    print("  Pipeline complete!")
    print()

    # Step 4: Display results
    print("=" * 70)
    print("Results Summary")
    print("=" * 70)
    print()

    print(f"Slate: {results['slate']['slate_id']}")
    print(f"Provider: {results['market']['provider']}")
    print()

    print("Statistics:")
    print(f"  - Games analyzed: {results['stats']['games_analyzed']}")
    print(f"  - Markets simulated: {results['stats']['markets_simulated']}")
    print(f"  - Picks generated: {results['stats']['total_picks']}")
    print()

    if results['picks']:
        print("Top Picks:")
        print("-" * 70)

        for i, pick in enumerate(results['picks'][:5], 1):
            print(f"\n{i}. {pick['player_name']} - {pick['market']} {pick['side']} {pick['line']}")
            print(f"   Win Probability: {pick['win_probability']:.1%}")
            print(f"   Edge: {pick['edge']:.2%}")
            print(f"   Expected Value: ${pick['expected_value']:.2f}")
            print(f"   Sharpe Ratio: {pick['sharpe_ratio']:.3f}")
    else:
        print("No picks met the minimum edge threshold.")

    print()
    print("=" * 70)

    # Step 5: Provenance inspection
    print("Provenance Information")
    print("=" * 70)
    print()

    print("Reset Policy:")
    for key, value in results['provenance']['reset_policy'].items():
        print(f"  - {key}: {value}")
    print()

    print("Input Fingerprints:")
    for key, value in results['provenance']['inputs'].items():
        if 'fingerprint' in key:
            print(f"  - {key}: {value[:16]}...")
        else:
            print(f"  - {key}: {value}")
    print()

    # Step 6: Export state
    print("=" * 70)
    print("Exporting State")
    print("=" * 70)
    print()

    state_export = runner.export_state()

    # Save to file
    export_path = "slate_state_export.json"
    with open(export_path, "w") as f:
        json.dump(state_export, f, indent=2)

    print(f"State exported to: {export_path}")
    print(f"Export size: {len(json.dumps(state_export))} bytes")
    print()

    print("=" * 70)
    print("Example Complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()
