"""
Correction fitting logic for CCM.

Learns context-specific residual corrections using shrinkage estimation.
"""

import math
from collections import defaultdict
from typing import Optional

import numpy as np

from hollersports.calibration.venue_coach_adjustments.models import (
    PropRecord,
    GameContext,
    CorrectionEntry,
    CorrectionMap,
    PropMarket,
    Provenance,
)
from hollersports.calibration.venue_coach_adjustments.feature_builder import (
    build_features,
    make_correction_key,
)


def compute_residual(record: PropRecord) -> float:
    """
    Compute residual: actual - line.

    This is side-agnostic; the CCM estimates expected bias.
    Selection logic separately decides higher/lower.

    Args:
        record: PropRecord with line and actual

    Returns:
        Residual value (positive = line was too low, negative = too high)
    """
    return record.actual - record.line


def compute_mad(values: list[float]) -> float:
    """
    Compute Median Absolute Deviation (MAD).

    More robust than std dev to outliers.

    Args:
        values: List of numeric values

    Returns:
        MAD statistic
    """
    if not values:
        return 0.0
    median = float(np.median(values))
    deviations = [abs(v - median) for v in values]
    return float(np.median(deviations))


def fit_corrections(
    records: list[PropRecord],
    contexts: list[GameContext],
    config: Optional[dict] = None,
    seed: int = 1337,
) -> dict[tuple, dict]:
    """
    Fit context-specific residual corrections with shrinkage.

    Groups records by context key, computes residual statistics,
    and applies shrinkage toward zero based on sample size.

    Args:
        records: List of PropRecords
        contexts: List of GameContexts (must match records 1:1)
        config: Config dict with shrinkage parameters
        seed: Random seed (for deterministic tie-breaking if needed)

    Returns:
        Dict mapping correction key tuple to stats dict

    Raises:
        ValueError: If records/contexts lengths don't match
    """
    if len(records) != len(contexts):
        raise ValueError(f"Records ({len(records)}) and contexts ({len(contexts)}) must match")

    if config is None:
        config = {}

    # Extract config parameters
    shrinkage_k = config.get("shrinkage", {}).get("k", 25)
    min_samples = config.get("shrinkage", {}).get("min_samples", 5)

    # Set numpy seed for determinism
    np.random.seed(seed)

    # Group residuals by context key
    groups = defaultdict(list)

    for record, context in zip(records, contexts):
        residual = compute_residual(record)
        features = build_features(record, context, config)
        key = make_correction_key(features, include_coach=True, include_timezone=True)
        groups[key].append(residual)

    # Compute statistics for each group
    corrections = {}

    for key, residuals in groups.items():
        count = len(residuals)

        # Skip if too few samples
        if count < min_samples:
            continue

        # Compute raw statistics
        mean_residual = float(np.mean(residuals))
        median_residual = float(np.median(residuals))
        dispersion = compute_mad(residuals)

        # Apply shrinkage toward zero
        shrinkage_factor = count / (count + shrinkage_k)
        mean_delta = mean_residual * shrinkage_factor

        # Compute confidence (saturates at 0.95)
        confidence = min(0.95, math.sqrt(count) / math.sqrt(count + shrinkage_k))

        corrections[key] = {
            "mean_delta": mean_delta,
            "median_delta": median_residual,
            "count": count,
            "confidence": confidence,
            "dispersion": dispersion,
        }

    return corrections


def corrections_to_entries(corrections: dict[tuple, dict]) -> list[CorrectionEntry]:
    """
    Convert corrections dict to list of CorrectionEntry objects.

    Args:
        corrections: Dict from fit_corrections()

    Returns:
        List of CorrectionEntry dataclasses
    """
    entries = []

    for key, stats in corrections.items():
        market_str, venue_bucket, coach_bucket, is_home, travel_b2b, timezone_bucket = key

        entry = CorrectionEntry(
            market=PropMarket(market_str),
            venue_bucket=venue_bucket,
            coach_bucket=coach_bucket,
            is_home=is_home,
            travel_b2b=travel_b2b,
            timezone_bucket=timezone_bucket,
            mean_delta=stats["mean_delta"],
            median_delta=stats["median_delta"],
            count=stats["count"],
            confidence=stats["confidence"],
            dispersion=stats["dispersion"],
        )
        entries.append(entry)

    return entries


def build_correction_map(
    records: list[PropRecord],
    contexts: list[GameContext],
    provenance: Provenance,
    config: dict,
    seed: int = 1337,
) -> CorrectionMap:
    """
    Build complete CorrectionMap from training data.

    This is the main entry point for creating a CCM artifact.

    Args:
        records: List of PropRecords
        contexts: List of GameContexts (must match records 1:1)
        provenance: Provenance metadata
        config: Configuration dict
        seed: Random seed

    Returns:
        CorrectionMap object ready for persistence

    Example:
        >>> ccm = build_correction_map(records, contexts, prov, config)
        >>> len(ccm)
        147  # Number of correction entries
    """
    # Fit corrections
    corrections = fit_corrections(records, contexts, config, seed)

    # Convert to CorrectionEntry objects
    entries = corrections_to_entries(corrections)

    # Build CorrectionMap
    ccm = CorrectionMap(
        provenance=provenance,
        config=config,
        corrections=entries,
    )

    return ccm
