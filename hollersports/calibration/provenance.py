"""
Provenance tracking utilities for deterministic, auditable calibration runs.

All CCM artifacts include provenance metadata to ensure:
- Reproducibility (same inputs + config + seed → same outputs)
- Auditability (track what data/config produced each artifact)
- Versioning (track schema/code versions)
"""

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from hollersports.calibration.venue_coach_adjustments.models import Provenance


def compute_stable_hash(data: Any) -> str:
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


def compute_file_hash(file_path: Path) -> str:
    """
    Compute deterministic hash of a file.

    Args:
        file_path: Path to file

    Returns:
        Hex string (first 16 characters of SHA-256)
    """
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()[:16]


def compute_config_hash(config: dict) -> str:
    """
    Compute deterministic hash of configuration dict.

    Args:
        config: Configuration dictionary

    Returns:
        Hex string (first 16 characters of SHA-256)
    """
    return compute_stable_hash(config)


def get_git_sha() -> Optional[str]:
    """
    Attempt to get current git SHA (if in git repo).

    Returns:
        Git SHA string or None if not available
    """
    try:
        import subprocess
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2,
            cwd=Path(__file__).parent.parent.parent.parent,
        )
        if result.returncode == 0:
            return result.stdout.strip()[:8]
    except Exception:
        pass
    return None


def create_provenance(
    inputs_path: Optional[Path] = None,
    inputs_data: Optional[list] = None,
    config: Optional[dict] = None,
    seed: int = 1337,
    schema_version: str = "1.0.0",
) -> Provenance:
    """
    Create provenance record for a calibration run.

    Args:
        inputs_path: Path to input file (will be hashed)
        inputs_data: Or raw input data (will be hashed)
        config: Configuration dict
        seed: Random seed
        schema_version: Schema version string

    Returns:
        Provenance object with all metadata

    Raises:
        ValueError: If neither inputs_path nor inputs_data provided
    """
    if inputs_path is None and inputs_data is None:
        raise ValueError("Must provide either inputs_path or inputs_data")

    # Compute inputs hash
    if inputs_path:
        inputs_hash = compute_file_hash(inputs_path)
    else:
        inputs_hash = compute_stable_hash(inputs_data)

    # Compute config hash
    config_hash = compute_config_hash(config or {})

    # Generate run ID
    run_id = str(uuid.uuid4())[:8]

    # Get current timestamp
    created_at = datetime.now(timezone.utc).isoformat()

    # Try to get git SHA
    git_sha = get_git_sha()

    return Provenance(
        run_id=run_id,
        created_at=created_at,
        seed=seed,
        inputs_hash=inputs_hash,
        config_hash=config_hash,
        schema_version=schema_version,
        git_sha=git_sha,
    )


def provenance_to_dict(prov: Provenance) -> dict:
    """Convert Provenance object to dict for JSON serialization."""
    return {
        "run_id": prov.run_id,
        "created_at": prov.created_at,
        "seed": prov.seed,
        "inputs_hash": prov.inputs_hash,
        "config_hash": prov.config_hash,
        "schema_version": prov.schema_version,
        "git_sha": prov.git_sha,
    }


def provenance_from_dict(data: dict) -> Provenance:
    """Create Provenance object from dict."""
    return Provenance(**data)
