"""
CLI interface for NFL SCMF engine.

Simple command-line runner for testing and backtest mode.
"""

import json
import sys
from typing import List
from hollersports.nfl.types import NFLGameRow, PropLeg, Market, Side
from hollersports.nfl.picker import pick_slate


def load_data_from_json(file_path: str) -> List[NFLGameRow]:
    """
    Load NFL data from JSON file.

    Expected format:
    [
        {
            "game_id": "...",
            "date": "YYYY-MM-DD",
            "team": "...",
            "opponent": "...",
            "is_home": 0 or 1,
            "player_id": "...",
            "player_name": "...",
            "position": "...",
            "snaps": int,
            "targets": int,
            "receptions": int,
            "receiving_yards": float,
            "rushing_attempts": int,
            "rushing_yards": float,
            ...
        }
    ]
    """
    with open(file_path, "r") as f:
        data_dict = json.load(f)

    rows = []
    for record in data_dict:
        row = NFLGameRow(
            game_id=record["game_id"],
            date=record["date"],
            team=record["team"],
            opponent=record["opponent"],
            is_home=record["is_home"],
            player_id=record["player_id"],
            player_name=record["player_name"],
            position=record["position"],
            snaps=record["snaps"],
            targets=record["targets"],
            receptions=record["receptions"],
            receiving_yards=record["receiving_yards"],
            rushing_attempts=record["rushing_attempts"],
            rushing_yards=record["rushing_yards"],
            routes=record.get("routes"),
            pass_attempts=record.get("pass_attempts"),
            pass_yards=record.get("pass_yards"),
            vegas_spread=record.get("vegas_spread"),
            vegas_total=record.get("vegas_total"),
            team_pass_rate_over_expected=record.get("team_pass_rate_over_expected"),
            opponent_pass_def_proxy=record.get("opponent_pass_def_proxy"),
            opponent_rush_def_proxy=record.get("opponent_rush_def_proxy"),
            line=record.get("line"),
        )
        rows.append(row)

    return rows


def load_props_from_json(file_path: str) -> List[PropLeg]:
    """
    Load props from JSON file.

    Expected format:
    [
        {
            "player_id": "...",
            "player_name": "...",
            "market": "RECEPTIONS",
            "line": 5.5,
            "side": "HIGHER",
            "game_id": "..."
        }
    ]
    """
    with open(file_path, "r") as f:
        props_dict = json.load(f)

    props = []
    for record in props_dict:
        prop = PropLeg(
            player_id=record["player_id"],
            player_name=record["player_name"],
            market=Market[record["market"]],
            line=record["line"],
            side=Side[record["side"]],
            game_id=record.get("game_id"),
        )
        props.append(prop)

    return props


def main():
    """
    Main CLI entry point.

    Usage:
        python -m hollersports.nfl.cli <data.json> <props.json> <slate_games.json> [config.json]
    """
    if len(sys.argv) < 4:
        print("Usage: python -m hollersports.nfl.cli <data.json> <props.json> <slate_games.json> [config.json]")
        sys.exit(1)

    data_file = sys.argv[1]
    props_file = sys.argv[2]
    slate_file = sys.argv[3]
    config_file = sys.argv[4] if len(sys.argv) > 4 else None

    # Load data
    print(f"Loading data from {data_file}...")
    all_data = load_data_from_json(data_file)
    print(f"Loaded {len(all_data)} player-game records")

    # Load props
    print(f"Loading props from {props_file}...")
    props = load_props_from_json(props_file)
    print(f"Loaded {len(props)} props")

    # Load slate games
    print(f"Loading slate from {slate_file}...")
    with open(slate_file, "r") as f:
        slate_games = json.load(f)
    print(f"Slate games: {slate_games}")

    # Load config (or use defaults)
    if config_file:
        print(f"Loading config from {config_file}...")
        with open(config_file, "r") as f:
            config = json.load(f)
    else:
        print("Using default config...")
        config = {
            "seed": 1337,
            "n_sims": 150000,
            "min_confidence": 0.65,
            "min_p_hit": 0.60,
            "ultra_safe_mode": True,
        }

    # Run picker
    print("\n=== Running NFL SCMF Picker ===\n")
    result = pick_slate(slate_games, props, all_data, config)

    # Print results
    print(f"Total candidates: {result.total_candidates}")
    print(f"Filtered candidates: {result.filtered_candidates}")
    print(f"Provenance hash: {result.provenance_hash}\n")

    print("=== Ultra-Safe 3-Leg ===")
    for i, proj in enumerate(result.ultra_safe_3leg, 1):
        print(f"{i}. {proj.player_name} ({proj.position}) - {proj.market.value} {proj.side.value} {proj.line}")
        print(f"   P(hit): {proj.p_hit:.1%}, Confidence: {proj.confidence:.1%}")
        print(f"   Median: {proj.median:.1f}, Floor: {proj.floor:.1f}")
        print()

    print("\n=== Ultra-Safe 5-Leg ===")
    for i, proj in enumerate(result.ultra_safe_5leg, 1):
        print(f"{i}. {proj.player_name} ({proj.position}) - {proj.market.value} {proj.side.value} {proj.line}")
        print(f"   P(hit): {proj.p_hit:.1%}, Confidence: {proj.confidence:.1%}")
        print(f"   Median: {proj.median:.1f}, Floor: {proj.floor:.1f}")
        print()


if __name__ == "__main__":
    main()
