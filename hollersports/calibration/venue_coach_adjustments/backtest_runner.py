"""
Backtest runner for Contextual Correction Maps (CCM).

Trains CCM on historical data and evaluates performance on held-out test set.
"""

import json
from pathlib import Path
from typing import Tuple, Optional
from datetime import datetime

import numpy as np

from hollersports.calibration.venue_coach_adjustments.models import (
    PropRecord,
    GameContext,
    PropMarket,
    PropSide,
    CorrectionMap,
)
from hollersports.calibration.venue_coach_adjustments.correction_fit import (
    build_correction_map,
    compute_residual,
)
from hollersports.calibration.venue_coach_adjustments.feature_builder import (
    build_features,
    make_correction_key,
)
from hollersports.calibration.apply_adjustments import get_delta
from hollersports.calibration.provenance import create_provenance


def load_data_from_jsonl(path: Path) -> Tuple[list[PropRecord], list[GameContext]]:
    """
    Load PropRecords and GameContexts from JSONL file.

    Expected format: one JSON object per line with fields matching
    PropRecord and GameContext schemas.

    Args:
        path: Path to JSONL file

    Returns:
        Tuple of (records, contexts) lists

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If data is malformed
    """
    records = []
    contexts = []

    with open(path, "r") as f:
        for line_num, line in enumerate(f, 1):
            try:
                data = json.loads(line)

                # Parse PropRecord
                record = PropRecord(
                    player_id=data["player_id"],
                    game_id=data["game_id"],
                    market=PropMarket(data["market"]),
                    line=float(data["line"]),
                    actual=float(data["actual"]),
                    side=PropSide(data["side"]),
                    timestamp=data["timestamp"],
                    team_id=data["team_id"],
                    opp_id=data["opp_id"],
                    venue_id=data["venue_id"],
                    hit=data.get("hit"),
                    model_projection=data.get("model_projection"),
                    minutes_expected=data.get("minutes_expected"),
                )

                # Parse GameContext
                context = GameContext(
                    venue_id=data["venue_id"],
                    is_home=data["is_home"],
                    team_id=data["team_id"],
                    opp_id=data["opp_id"],
                    travel_b2b=data.get("travel_b2b"),
                    travel_distance_km=data.get("travel_distance_km"),
                    timezone_delta=data.get("timezone_delta"),
                    rest_days=data.get("rest_days"),
                    coach_id=data.get("coach_id"),
                    rotation_depth_proxy=data.get("rotation_depth_proxy"),
                    pace_proxy=data.get("pace_proxy"),
                    opponent_defense_proxy=data.get("opponent_defense_proxy"),
                    scheme_proxy=data.get("scheme_proxy"),
                )

                records.append(record)
                contexts.append(context)

            except Exception as e:
                raise ValueError(f"Error parsing line {line_num}: {e}") from e

    return records, contexts


def time_based_split(
    records: list[PropRecord],
    contexts: list[GameContext],
    train_fraction: float = 0.8,
) -> Tuple[list[PropRecord], list[GameContext], list[PropRecord], list[GameContext]]:
    """
    Split data into train/test by timestamp (time-based, no data leakage).

    Args:
        records: List of PropRecords
        contexts: List of GameContexts
        train_fraction: Fraction for training (0.0 to 1.0)

    Returns:
        Tuple of (train_records, train_contexts, test_records, test_contexts)
    """
    # Sort by timestamp
    sorted_pairs = sorted(zip(records, contexts), key=lambda x: x[0].timestamp)

    # Split
    split_idx = int(len(sorted_pairs) * train_fraction)

    train_pairs = sorted_pairs[:split_idx]
    test_pairs = sorted_pairs[split_idx:]

    train_records = [p[0] for p in train_pairs]
    train_contexts = [p[1] for p in train_pairs]
    test_records = [p[0] for p in test_pairs]
    test_contexts = [p[1] for p in test_pairs]

    return train_records, train_contexts, test_records, test_contexts


def evaluate_simple_decision_rule(
    records: list[PropRecord],
    contexts: list[GameContext],
    ccm: Optional[CorrectionMap] = None,
    config: Optional[dict] = None,
) -> dict:
    """
    Evaluate simple decision rule: pick higher if projection > line, else lower.

    If CCM provided, uses adjusted projections. Otherwise uses raw projections.
    If no projections available, returns "insufficient" status.

    Args:
        records: List of PropRecords
        contexts: List of GameContexts
        ccm: Optional CorrectionMap for adjustments
        config: Optional config

    Returns:
        Evaluation metrics dict
    """
    if not records:
        return {
            "total": 0,
            "hit_rate": float("nan"),
            "mae": float("nan"),
            "status": "no_data",
        }

    # Check if projections available
    has_projections = any(r.model_projection is not None for r in records)

    if not has_projections:
        # Can only compute baseline using line itself (no predictive value)
        return {
            "total": len(records),
            "hit_rate": float("nan"),
            "mae": float("nan"),
            "status": "no_projections",
        }

    # Evaluate
    correct = 0
    residual_errors = []

    for record, context in zip(records, contexts):
        if record.model_projection is None:
            continue

        # Get projection (raw or adjusted)
        projection = record.model_projection

        if ccm:
            delta, confidence = get_delta(ccm, record.market, context, record, config)
            projection = projection + delta

        # Make decision
        predicted_higher = projection > record.line

        # Check if correct
        actual_higher = record.actual > record.line
        if predicted_higher == actual_higher:
            correct += 1

        # Compute residual error
        predicted_residual = projection - record.line
        actual_residual = record.actual - record.line
        residual_error = abs(predicted_residual - actual_residual)
        residual_errors.append(residual_error)

    hit_rate = correct / len(records) if records else 0.0
    mae = float(np.mean(residual_errors)) if residual_errors else float("nan")

    return {
        "total": len(records),
        "correct": correct,
        "hit_rate": hit_rate,
        "mae": mae,
        "status": "ok",
    }


def run_backtest(
    input_path: Path,
    output_dir: Path,
    config: dict,
    seed: int = 1337,
    train_fraction: float = 0.8,
) -> dict:
    """
    Run full backtest: load data, train CCM, evaluate on test set.

    Args:
        input_path: Path to input JSONL file
        output_dir: Directory for output artifacts
        config: Configuration dict
        seed: Random seed
        train_fraction: Fraction of data for training

    Returns:
        Backtest report dict

    Side effects:
        - Saves correction_maps.json to output_dir
        - Saves backtest_report.json to output_dir
    """
    # Load data
    records, contexts = load_data_from_jsonl(input_path)

    # Create provenance
    provenance = create_provenance(
        inputs_path=input_path,
        config=config,
        seed=seed,
    )

    # Split data
    train_records, train_contexts, test_records, test_contexts = time_based_split(
        records, contexts, train_fraction
    )

    # Build CCM on training data
    ccm = build_correction_map(train_records, train_contexts, provenance, config, seed)

    # Evaluate on test set
    baseline_metrics = evaluate_simple_decision_rule(test_records, test_contexts, ccm=None, config=config)
    corrected_metrics = evaluate_simple_decision_rule(test_records, test_contexts, ccm=ccm, config=config)

    # Build report
    report = {
        "provenance": {
            "run_id": provenance.run_id,
            "created_at": provenance.created_at,
            "seed": provenance.seed,
            "inputs_hash": provenance.inputs_hash,
            "config_hash": provenance.config_hash,
            "git_sha": provenance.git_sha,
        },
        "data": {
            "total_records": len(records),
            "train_records": len(train_records),
            "test_records": len(test_records),
            "train_fraction": train_fraction,
        },
        "ccm": {
            "total_corrections": len(ccm),
        },
        "baseline": baseline_metrics,
        "corrected": corrected_metrics,
        "improvement": {
            "hit_rate_delta": corrected_metrics["hit_rate"] - baseline_metrics["hit_rate"]
            if baseline_metrics["status"] == "ok" and corrected_metrics["status"] == "ok"
            else float("nan"),
            "mae_delta": baseline_metrics["mae"] - corrected_metrics["mae"]
            if baseline_metrics["status"] == "ok" and corrected_metrics["status"] == "ok"
            else float("nan"),
        },
    }

    # Save artifacts
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save CCM
    from hollersports.calibration.apply_adjustments import save_ccm
    ccm_path = output_dir / "correction_maps.json"
    save_ccm(ccm, ccm_path)

    # Save report
    report_path = output_dir / "backtest_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    return report
