"""
Feature builder for Contextual Correction Maps (CCM).

Converts PropRecord + GameContext into deterministic feature vectors
with categorical hashing to bound map size.
"""

import hashlib
from typing import Optional

from hollersports.calibration.venue_coach_adjustments.models import (
    PropRecord,
    GameContext,
    PropMarket,
)


# Default bucket sizes (from schema.yaml)
DEFAULT_BUCKETS = {
    "venue": 100,
    "coach": 50,
    "team": 32,
    "opponent": 32,
    "scheme": 10,
}


def stable_hash_to_bucket(value: str, buckets: int, salt: str = "ccm_v1") -> int:
    """
    Hash a categorical value to a deterministic bucket.

    Uses SHA-256 for stability across platforms and Python versions.

    Args:
        value: String value to hash
        buckets: Number of buckets (0 to buckets-1)
        salt: Salt string for domain separation

    Returns:
        Bucket index (0 to buckets-1)

    Example:
        >>> stable_hash_to_bucket("TD_Garden", 100, "venue")
        42  # Always returns same value
    """
    payload = f"{salt}:{value}".encode("utf-8")
    hash_bytes = hashlib.sha256(payload).digest()
    # Convert first 8 bytes to int
    hash_int = int.from_bytes(hash_bytes[:8], byteorder="big")
    return hash_int % buckets


def bucket_timezone(timezone_delta: Optional[int]) -> int:
    """
    Bucket timezone delta into coarse categories.

    Bins: [-12, -3, -1, 1, 3, 12] → buckets: [-2, -1, 0, 1, 2]

    Args:
        timezone_delta: Timezone difference in hours (-12 to +12)

    Returns:
        Bucket index (-2 to 2, or 0 if None)
    """
    if timezone_delta is None:
        return 0

    if timezone_delta <= -3:
        return -2
    elif timezone_delta <= -1:
        return -1
    elif timezone_delta >= 3:
        return 2
    elif timezone_delta >= 1:
        return 1
    else:
        return 0


def build_features(
    record: PropRecord,
    context: GameContext,
    config: Optional[dict] = None,
) -> dict:
    """
    Build deterministic feature vector from PropRecord + GameContext.

    Features are split into:
    - Categorical (hashed to buckets): venue, coach, team, opponent, scheme
    - Binary: is_home, travel_b2b
    - Numeric: rest_days, travel_distance_km, rotation_depth, pace, opp_defense
    - Bucketed: timezone_delta

    Args:
        record: PropRecord with line, actual, market
        context: GameContext with venue, travel, coaching metadata
        config: Optional config dict with bucket sizes

    Returns:
        Feature dict with deterministic keys/values

    Example:
        >>> features = build_features(record, context)
        >>> features["venue_bucket"]
        42
        >>> features["is_home"]
        1
    """
    if config is None:
        config = {"hash_buckets": DEFAULT_BUCKETS}

    buckets = config.get("hash_buckets", DEFAULT_BUCKETS)

    # Categorical features (hashed)
    venue_bucket = stable_hash_to_bucket(
        context.venue_id,
        buckets.get("venue", 100),
        salt="venue",
    )

    coach_bucket = -1  # Default if no coach
    if context.coach_id:
        coach_bucket = stable_hash_to_bucket(
            context.coach_id,
            buckets.get("coach", 50),
            salt="coach",
        )

    team_bucket = stable_hash_to_bucket(
        context.team_id,
        buckets.get("team", 32),
        salt="team",
    )

    opp_bucket = stable_hash_to_bucket(
        context.opp_id,
        buckets.get("opponent", 32),
        salt="opponent",
    )

    scheme_bucket = -1  # Default if no scheme
    if context.scheme_proxy:
        scheme_bucket = stable_hash_to_bucket(
            context.scheme_proxy,
            buckets.get("scheme", 10),
            salt="scheme",
        )

    # Binary features
    is_home = 1 if context.is_home else 0
    travel_b2b = 1 if context.travel_b2b else 0

    # Bucketed features
    timezone_bucket = bucket_timezone(context.timezone_delta)

    # Numeric features (kept as-is)
    rest_days = context.rest_days if context.rest_days is not None else 1
    travel_distance_km = context.travel_distance_km if context.travel_distance_km is not None else 0.0
    rotation_depth = context.rotation_depth_proxy if context.rotation_depth_proxy is not None else 0.5
    pace = context.pace_proxy if context.pace_proxy is not None else 0.0
    opp_defense = context.opponent_defense_proxy if context.opponent_defense_proxy is not None else 0.0

    return {
        # Market
        "market": record.market.value,

        # Categorical (hashed)
        "venue_bucket": venue_bucket,
        "coach_bucket": coach_bucket,
        "team_bucket": team_bucket,
        "opp_bucket": opp_bucket,
        "scheme_bucket": scheme_bucket,

        # Binary
        "is_home": is_home,
        "travel_b2b": travel_b2b,

        # Bucketed
        "timezone_bucket": timezone_bucket,

        # Numeric
        "rest_days": rest_days,
        "travel_distance_km": travel_distance_km,
        "rotation_depth": rotation_depth,
        "pace": pace,
        "opp_defense": opp_defense,
    }


def make_correction_key(
    features: dict,
    include_coach: bool = True,
    include_timezone: bool = True,
    include_scheme: bool = True,
) -> tuple:
    """
    Create hashable key tuple for correction lookup.

    Allows progressive fallback by omitting optional features.

    Args:
        features: Feature dict from build_features()
        include_coach: Include coach_bucket in key
        include_timezone: Include timezone_bucket in key
        include_scheme: Include scheme_bucket in key

    Returns:
        Tuple for use as dict key

    Example:
        >>> key = make_correction_key(features)
        ('PTS', 42, 7, 1, 0, 0)  # (market, venue, coach, home, b2b, tz)
    """
    market = features["market"]
    venue_bucket = features["venue_bucket"]
    coach_bucket = features["coach_bucket"] if include_coach else -1
    is_home = features["is_home"]
    travel_b2b = features["travel_b2b"]
    timezone_bucket = features["timezone_bucket"] if include_timezone else 0

    return (
        market,
        venue_bucket,
        coach_bucket,
        is_home,
        travel_b2b,
        timezone_bucket,
    )
