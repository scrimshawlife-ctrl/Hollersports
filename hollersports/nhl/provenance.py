"""
Provenance tracking for NHL SOG engine.

Ensures deterministic, reproducible projections with full audit trail.
"""

import hashlib
import json
from typing import Any, List
from hollersports.nhl.types import NHLGameRow


def stable_hash(data: Any) -> str:
    """
    Compute deterministic SHA-256 hash of arbitrary data.

    Args:
        data: Any JSON-serializable data

    Returns:
        Hex string (first 16 characters of SHA-256)
    """
    if isinstance(data, (str, bytes)):
        payload = data.encode("utf-8") if isinstance(data, str) else data
    else:
        payload = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")

    return hashlib.sha256(payload).hexdigest()[:16]


def compute_dataset_fingerprint(rows: List[NHLGameRow]) -> str:
    """
    Compute deterministic fingerprint of input dataset.

    Sorts by (game_id, player_id, date) to ensure stable ordering.

    Args:
        rows: List of NHLGameRow observations

    Returns:
        Dataset fingerprint hash
    """
    # Sort for determinism
    sorted_rows = sorted(rows, key=lambda r: (r.game_id, r.player_id, r.date))

    # Create fingerprint from key fields
    fingerprint_data = [
        {
            "game_id": r.game_id,
            "player_id": r.player_id,
            "date": r.date,
            "sog": r.sog,
            "toi": r.toi_minutes,
        }
        for r in sorted_rows
    ]

    return stable_hash(fingerprint_data)


def compute_config_hash(config: dict) -> str:
    """
    Compute deterministic hash of configuration.

    Args:
        config: Configuration dictionary

    Returns:
        Config hash
    """
    return stable_hash(config)


def compute_projection_provenance(
    player_id: str,
    game_id: str,
    dataset_fingerprint: str,
    config_hash: str,
    seed: int,
    normalizer_hash: str = "nhl_v1",
) -> str:
    """
    Compute provenance hash for a single projection.

    Args:
        player_id: Player identifier
        game_id: Game identifier
        dataset_fingerprint: Hash of input dataset
        config_hash: Hash of configuration
        seed: Random seed
        normalizer_hash: Hash of AAL-core normalizer

    Returns:
        Provenance hash uniquely identifying this projection
    """
    provenance_data = {
        "player_id": player_id,
        "game_id": game_id,
        "dataset_fingerprint": dataset_fingerprint,
        "config_hash": config_hash,
        "seed": seed,
        "normalizer_hash": normalizer_hash,
    }

    return stable_hash(provenance_data)
