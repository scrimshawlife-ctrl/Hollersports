"""
Runtime application of Contextual Correction Maps (CCM).

Provides simple interface for loading CCM and applying corrections to projections.
"""

import json
import os
from pathlib import Path
from typing import Optional, Tuple

from hollersports.calibration.venue_coach_adjustments.models import (
    PropRecord,
    GameContext,
    CorrectionMap,
    CorrectionEntry,
    PropMarket,
    Provenance,
)
from hollersports.calibration.venue_coach_adjustments.feature_builder import (
    build_features,
    make_correction_key,
)
from hollersports.calibration.provenance import provenance_from_dict


# Global CCM instance (loaded once, reused)
_GLOBAL_CCM: Optional[CorrectionMap] = None

# Config toggle
CCM_ENABLED = os.getenv("HOLLERSPORTS_CCM_ENABLED", "true").lower() == "true"


def load_ccm(path: Path) -> CorrectionMap:
    """
    Load CorrectionMap from JSON file.

    Args:
        path: Path to correction_maps.json

    Returns:
        CorrectionMap object

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If JSON is malformed
    """
    with open(path, "r") as f:
        data = json.load(f)

    # Parse provenance
    provenance = provenance_from_dict(data["provenance"])

    # Parse config
    config = data["config"]

    # Parse corrections
    corrections = []
    for entry_data in data["corrections"]:
        entry = CorrectionEntry(
            market=PropMarket(entry_data["market"]),
            venue_bucket=entry_data["venue_bucket"],
            coach_bucket=entry_data["coach_bucket"],
            is_home=entry_data["is_home"],
            travel_b2b=entry_data["travel_b2b"],
            timezone_bucket=entry_data["timezone_bucket"],
            mean_delta=entry_data["mean_delta"],
            median_delta=entry_data["median_delta"],
            count=entry_data["count"],
            confidence=entry_data["confidence"],
            dispersion=entry_data["dispersion"],
        )
        corrections.append(entry)

    return CorrectionMap(
        provenance=provenance,
        config=config,
        corrections=corrections,
    )


def save_ccm(ccm: CorrectionMap, path: Path) -> None:
    """
    Save CorrectionMap to JSON file.

    Args:
        ccm: CorrectionMap object
        path: Output path
    """
    from hollersports.calibration.provenance import provenance_to_dict

    data = {
        "provenance": provenance_to_dict(ccm.provenance),
        "config": ccm.config,
        "corrections": [
            {
                "market": entry.market.value,
                "venue_bucket": entry.venue_bucket,
                "coach_bucket": entry.coach_bucket,
                "is_home": entry.is_home,
                "travel_b2b": entry.travel_b2b,
                "timezone_bucket": entry.timezone_bucket,
                "mean_delta": entry.mean_delta,
                "median_delta": entry.median_delta,
                "count": entry.count,
                "confidence": entry.confidence,
                "dispersion": entry.dispersion,
            }
            for entry in ccm.corrections
        ],
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def get_delta(
    ccm: CorrectionMap,
    market: PropMarket,
    context: GameContext,
    record: PropRecord,
    config: Optional[dict] = None,
) -> Tuple[float, float]:
    """
    Get correction delta and confidence for a given context.

    Uses progressive fallback if exact key not found:
    1. Full key (venue + coach + timezone + home + b2b)
    2. Drop scheme/opponent (not in key anyway)
    3. Drop timezone
    4. Drop coach
    5. Venue-only + home
    6. Market-only (return 0 with very low confidence)

    Each fallback reduces confidence by decay factor (default 0.8).

    Args:
        ccm: CorrectionMap object
        market: PropMarket
        context: GameContext
        record: PropRecord (for feature building)
        config: Optional config (uses ccm.config if None)

    Returns:
        Tuple of (delta, confidence)

    Example:
        >>> delta, conf = get_delta(ccm, PropMarket.PTS, context, record)
        >>> delta
        -1.2  # Adjust projection down by 1.2
        >>> conf
        0.87  # 87% confidence
    """
    if config is None:
        config = ccm.config

    # Build features
    features = build_features(record, context, config)

    # Fallback confidence decay
    decay = config.get("fallback_confidence_decay", 0.8)

    # Fallback ladder
    fallback_specs = [
        {"include_coach": True, "include_timezone": True, "confidence_mult": 1.0},
        {"include_coach": True, "include_timezone": False, "confidence_mult": decay},
        {"include_coach": False, "include_timezone": False, "confidence_mult": decay ** 2},
    ]

    for spec in fallback_specs:
        key = make_correction_key(
            features,
            include_coach=spec["include_coach"],
            include_timezone=spec["include_timezone"],
        )
        entry = ccm.get_correction(key)

        if entry:
            delta = entry.mean_delta
            confidence = entry.confidence * spec["confidence_mult"]
            return delta, confidence

    # Final fallback: no correction
    return 0.0, 0.0


def apply_adjustment(
    projection: float,
    market: PropMarket,
    context: GameContext,
    record: PropRecord,
    ccm: Optional[CorrectionMap] = None,
    config: Optional[dict] = None,
) -> float:
    """
    Apply CCM adjustment to a raw projection.

    This is the main entry point for runtime use.

    Args:
        projection: Raw model projection
        market: PropMarket
        context: GameContext
        record: PropRecord (for feature building)
        ccm: CorrectionMap (uses global if None)
        config: Optional config

    Returns:
        Adjusted projection

    Example:
        >>> raw_projection = 25.0
        >>> adjusted = apply_adjustment(raw_projection, PropMarket.PTS, context, record)
        >>> adjusted
        23.8  # Adjusted down by 1.2
    """
    global _GLOBAL_CCM

    # Check if CCM is enabled
    if not CCM_ENABLED:
        return projection

    # Load global CCM if needed
    if ccm is None:
        if _GLOBAL_CCM is None:
            # Try to load from default path
            default_path = Path(__file__).parent / "venue_coach_adjustments" / "correction_maps.json"
            if not default_path.exists():
                # No CCM available, return raw projection
                return projection
            _GLOBAL_CCM = load_ccm(default_path)
        ccm = _GLOBAL_CCM

    # Get delta
    delta, confidence = get_delta(ccm, market, context, record, config)

    # Apply adjustment
    adjusted = projection + delta

    return adjusted


def initialize_ccm(path: Optional[Path] = None) -> None:
    """
    Initialize global CCM instance.

    Call this at application startup to pre-load CCM.

    Args:
        path: Path to correction_maps.json (uses default if None)
    """
    global _GLOBAL_CCM

    if path is None:
        path = Path(__file__).parent / "venue_coach_adjustments" / "correction_maps.json"

    if path.exists():
        _GLOBAL_CCM = load_ccm(path)
    else:
        _GLOBAL_CCM = None


def get_ccm_status() -> dict:
    """
    Get current CCM status for debugging/monitoring.

    Returns:
        Status dict with enabled flag, loaded state, entry count
    """
    global _GLOBAL_CCM

    return {
        "enabled": CCM_ENABLED,
        "loaded": _GLOBAL_CCM is not None,
        "entry_count": len(_GLOBAL_CCM) if _GLOBAL_CCM else 0,
        "provenance": {
            "run_id": _GLOBAL_CCM.provenance.run_id if _GLOBAL_CCM else None,
            "created_at": _GLOBAL_CCM.provenance.created_at if _GLOBAL_CCM else None,
        } if _GLOBAL_CCM else None,
    }
