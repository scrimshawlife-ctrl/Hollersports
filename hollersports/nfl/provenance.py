"""
Provenance tracking for NFL SCMF.

Deterministic hashing of script state + config for full audit trail.
"""

import hashlib
import json
from typing import Dict, Any


def compute_provenance_hash(
    player_id: str,
    game_id: str,
    market: str,
    line: float,
    side: str,
    script_priors: Dict[str, float],
    config: dict,
    dataset_fingerprint: str,
) -> str:
    """
    Compute deterministic provenance hash.

    Args:
        player_id: Player identifier
        game_id: Game identifier
        market: Market string
        line: Prop line
        side: Side string
        script_priors: Script state probabilities
        config: Full configuration dict
        dataset_fingerprint: Hash of input dataset

    Returns:
        SHA-256 hex digest
    """
    payload = {
        "player_id": player_id,
        "game_id": game_id,
        "market": market,
        "line": line,
        "side": side,
        "script_priors": script_priors,
        "config": _sanitize_config(config),
        "dataset_fingerprint": dataset_fingerprint,
        "version": "nfl_scmf_v1",
    }

    # Serialize to JSON with sorted keys
    json_str = json.dumps(payload, sort_keys=True, separators=(",", ":"))

    # SHA-256 hash
    hash_obj = hashlib.sha256(json_str.encode("utf-8"))
    return hash_obj.hexdigest()


def compute_dataset_fingerprint(data: list) -> str:
    """
    Compute fingerprint of input dataset.

    Args:
        data: List of NFLGameRow objects

    Returns:
        SHA-256 hex digest

    Simple model: hash count + first/last game IDs
    """
    if not data:
        return hashlib.sha256(b"empty_dataset").hexdigest()

    payload = {
        "count": len(data),
        "first_game_id": data[0].game_id if data else None,
        "last_game_id": data[-1].game_id if data else None,
    }

    json_str = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    hash_obj = hashlib.sha256(json_str.encode("utf-8"))
    return hash_obj.hexdigest()


def _sanitize_config(config: dict) -> Dict[str, Any]:
    """
    Sanitize config for hashing.

    Remove non-deterministic fields.
    """
    sanitized = {}

    # Include only deterministic config keys
    deterministic_keys = [
        "seed",
        "n_sims",
        "min_confidence",
        "min_p_hit",
        "min_role_score",
        "wr_min_routes",
        "wr_min_target_share",
        "te_min_routes",
        "te_min_target_share",
        "rb_min_snap_share",
        "rb_min_rush_share",
        "qb_min_snap_share",
        "opponent_max_adjustment",
        "home_field_boost",
        "ultra_safe_mode",
        "forbid_event_markets",
    ]

    for key in deterministic_keys:
        if key in config:
            sanitized[key] = config[key]

    return sanitized
