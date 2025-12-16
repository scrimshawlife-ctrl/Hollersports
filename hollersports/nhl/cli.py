"""
CLI interface for NHL SOG Picker.

Usage:
    python -m hollersports.nhl.cli --data slate.csv --mode ultra_safe
"""

import argparse
import sys
from pathlib import Path
from typing import List

import pandas as pd

from hollersports.nhl.types import NHLGameRow, SOGProp, Side
from hollersports.nhl.picker import pick_slate, DEFAULT_CONFIG


def load_data_from_csv(path: Path) -> List[NHLGameRow]:
    """
    Load NHL game data from CSV.

    Args:
        path: Path to CSV file

    Returns:
        List of NHLGameRow objects
    """
    df = pd.read_csv(path)

    rows = []
    for _, row_data in df.iterrows():
        row = NHLGameRow(
            game_id=str(row_data["game_id"]),
            date=str(row_data["date"]),
            team=str(row_data["team"]),
            opponent=str(row_data["opponent"]),
            is_home=int(row_data["is_home"]),
            player_id=str(row_data["player_id"]),
            player_name=str(row_data["player_name"]),
            position=str(row_data["position"]),
            toi_minutes=float(row_data["toi_minutes"]),
            sog=int(row_data["sog"]),
            pp_toi_minutes=float(row_data.get("pp_toi_minutes", 0)) if "pp_toi_minutes" in row_data else None,
            line_sog=float(row_data.get("line_sog", 0)) if "line_sog" in row_data else None,
        )
        rows.append(row)

    return rows


def print_slate_result(result, mode: str):
    """
    Print slate result in Bettor Console style.

    Args:
        result: SlatePickResult
        mode: Mode name
    """
    print("\n" + "=" * 80)
    print(f"NHL SOG PICKER - {mode.upper()} MODE")
    print("=" * 80)
    print(f"Total candidates: {result.total_candidates}")
    print(f"Filtered candidates: {result.filtered_candidates}")
    print()

    # Select appropriate slate based on mode
    if mode == "ultra_safe":
        slate = result.ultra_safe_5leg if len(result.ultra_safe_5leg) >= 3 else result.ultra_safe_3leg
        slate_name = "Ultra-Safe 5-Leg" if len(slate) >= 5 else "Ultra-Safe 3-Leg"
    elif mode == "balanced":
        slate = result.balanced_5leg if result.balanced_5leg else result.ultra_safe_5leg
        slate_name = "Balanced 5-Leg"
    elif mode == "correlated":
        slate = result.correlated_5leg if result.correlated_5leg else result.ultra_safe_5leg
        slate_name = "Correlated 5-Leg"
    else:
        slate = result.ultra_safe_3leg
        slate_name = "Ultra-Safe 3-Leg"

    print(f"{slate_name}:")
    print("-" * 80)

    for i, proj in enumerate(slate, 1):
        side_str = "OVER" if proj.side == Side.HIGHER else "UNDER"
        print(f"\n{i}. {proj.player_name} - {side_str} {proj.line}")
        print(f"   Game: {proj.game_id}")
        print(f"   Projection: μ={proj.mu:.2f}, floor={proj.floor:.2f}")
        print(f"   P(hit): {proj.p_hit:.1%} | Confidence: {proj.confidence:.1%}")
        print(f"   Role Score: {proj.role_score:.2f}")

        if proj.reasons:
            print(f"   Reasons: {', '.join(proj.reasons[:3])}")  # Top 3 reasons

        if proj.flags:
            print(f"   ⚠️  Flags: {', '.join(proj.flags)}")

    print("\n" + "=" * 80)
    print(f"Combined P(all hit): {prod([p.p_hit for p in slate]):.1%} (independent assumption)")
    print("=" * 80 + "\n")


def prod(values: List[float]) -> float:
    """Compute product of values."""
    result = 1.0
    for v in values:
        result *= v
    return result


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="NHL SOG Picker")
    parser.add_argument("--data", type=str, required=True, help="Path to input CSV")
    parser.add_argument("--mode", type=str, choices=["ultra_safe", "balanced", "correlated"], default="ultra_safe", help="Picking mode")
    parser.add_argument("--slate", type=str, help="Path to slate game IDs (one per line)")
    parser.add_argument("--min-confidence", type=float, default=0.55, help="Minimum confidence threshold")
    parser.add_argument("--min-p-hit", type=float, default=0.58, help="Minimum p_hit threshold")
    parser.add_argument("--seed", type=int, default=1337, help="Random seed")

    args = parser.parse_args()

    # Load data
    print(f"Loading data from {args.data}...")
    all_data = load_data_from_csv(Path(args.data))
    print(f"Loaded {len(all_data)} player-game observations")

    # Determine slate games
    if args.slate:
        with open(args.slate) as f:
            slate_games = [line.strip() for line in f if line.strip()]
    else:
        # Use all unique games in data
        slate_games = list(set(g.game_id for g in all_data))

    print(f"Slate contains {len(slate_games)} games")

    # Generate props from data (use line_sog if available, otherwise estimate)
    props = []
    for game in all_data:
        if game.game_id in slate_games:
            # Create both over and under props
            line = game.line_sog if game.line_sog else game.sog * 1.05  # Slight over baseline

            props.append(SOGProp(
                player_id=game.player_id,
                player_name=game.player_name,
                line=line,
                side=Side.HIGHER,
                game_id=game.game_id,
            ))

            props.append(SOGProp(
                player_id=game.player_id,
                player_name=game.player_name,
                line=line,
                side=Side.LOWER,
                game_id=game.game_id,
            ))

    # Remove duplicates
    unique_props = []
    seen = set()
    for prop in props:
        key = (prop.player_id, prop.line, prop.side, prop.game_id)
        if key not in seen:
            unique_props.append(prop)
            seen.add(key)

    print(f"Evaluating {len(unique_props)} prop candidates...")

    # Configure
    config = DEFAULT_CONFIG.copy()
    config.update({
        "min_confidence": args.min_confidence,
        "min_p_hit": args.min_p_hit,
        "seed": args.seed,
    })

    # Run picker
    print("Running picker...")
    result = pick_slate(slate_games, unique_props, all_data, config)

    # Print result
    print_slate_result(result, args.mode)


if __name__ == "__main__":
    main()
