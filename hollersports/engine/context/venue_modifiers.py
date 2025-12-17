# FILE: hollersports/engine/context/venue_modifiers.py
# ABX-Core / SEED-compliant: deterministic, bounded, provenance-embedded.
# Purpose: Provide arena/stadium/coaching context as *secondary* modifiers.
# Rule: These modifiers may adjust distribution width (sigma) and apply tiny bounded mean nudges,
# but may NEVER override the median-floor engine or inject narrative.

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple
import hashlib
import json


# -----------------------------
# Deterministic hashing utils
# -----------------------------

def _stable_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


# -----------------------------
# Config + records
# -----------------------------

@dataclass(frozen=True)
class ModifierConfig:
    """
    Guardrails for venue/coaching effects.
    """
    # Mean nudges are tiny and bounded, to ensure "context" stays secondary.
    max_mean_nudge_frac: float = 0.03      # +/- 3% on mu (and typically we apply half this)
    # Sigma multiplier bounds: context can widen/narrow distributions modestly.
    min_sigma_mult: float = 0.90
    max_sigma_mult: float = 1.12
    # If no record exists for a venue/coach pair, use neutral.
    default_mean_nudge_frac: float = 0.00
    default_sigma_mult: float = 1.00

    def fingerprint(self) -> str:
        return _sha256(_stable_json(self.__dict__))


@dataclass(frozen=True)
class VenueRecord:
    """
    Learned/backtested venue tendencies (NOT live scraped; derived from your dataset).
    Values are stored as bounded scalars.
    """
    venue_id: str
    sport: str

    # Mean nudge fraction applied to mu (bounded by config)
    mean_nudge_frac: float

    # Sigma multiplier applied to sigma (bounded by config)
    sigma_mult: float

    # Optional explanatory metadata (never used for decisions)
    meta: Dict[str, Any] = None


@dataclass(frozen=True)
class CoachRecord:
    """
    Coaching/rotation stability proxy. This is typically sigma shaping, not mu shaping.
    """
    coach_id: str
    sport: str
    sigma_mult: float
    mean_nudge_frac: float = 0.0
    meta: Dict[str, Any] = None


@dataclass(frozen=True)
class ModifierResult:
    """
    Output of applying context. This is what your spine consumes.
    """
    mu_adj: float
    sigma_adj: float
    mu_nudge_frac: float
    sigma_mult: float
    provenance_hash: str


# -----------------------------
# Library object (in-memory, deterministic)
# -----------------------------

class ModifierLibrary:
    """
    Holds backtested modifier records. Load from a JSON/YAML artifact you control.
    No web, no time-based behavior.
    """

    def __init__(
        self,
        *,
        sport: str,
        config: Optional[ModifierConfig] = None,
        venues: Optional[Dict[str, VenueRecord]] = None,
        coaches: Optional[Dict[str, CoachRecord]] = None,
    ) -> None:
        self.sport = sport
        self.config = config or ModifierConfig()
        self.venues: Dict[str, VenueRecord] = venues or {}
        self.coaches: Dict[str, CoachRecord] = coaches or {}

    def fingerprint(self) -> str:
        """
        Stable fingerprint of the library contents + config.
        """
        payload = {
            "sport": self.sport,
            "config": self.config.__dict__,
            "venues": {k: v.__dict__ for k, v in sorted(self.venues.items())},
            "coaches": {k: v.__dict__ for k, v in sorted(self.coaches.items())},
        }
        return _sha256(_stable_json(payload))


# -----------------------------
# Core application
# -----------------------------

def apply_context_modifiers(
    *,
    lib: ModifierLibrary,
    mu: float,
    sigma: float,
    venue_id: Optional[str],
    coach_id: Optional[str],
) -> ModifierResult:
    """
    Apply venue + coach effects to (mu, sigma) in a bounded, secondary way.
    Mean nudges are intentionally small; sigma shaping is the primary channel.

    This function is deterministic: same inputs -> same outputs.
    """
    cfg = lib.config

    # Start neutral
    venue_mu = cfg.default_mean_nudge_frac
    venue_sigma = cfg.default_sigma_mult
    coach_mu = 0.0
    coach_sigma = 1.0

    if venue_id and venue_id in lib.venues:
        vr = lib.venues[venue_id]
        if vr.sport != lib.sport:
            # ignore mismatched record
            pass
        else:
            venue_mu = float(vr.mean_nudge_frac)
            venue_sigma = float(vr.sigma_mult)

    if coach_id and coach_id in lib.coaches:
        cr = lib.coaches[coach_id]
        if cr.sport != lib.sport:
            pass
        else:
            coach_mu = float(cr.mean_nudge_frac)
            coach_sigma = float(cr.sigma_mult)

    # Combine effects: mu nudge adds; sigma multipliers multiply.
    mu_nudge = venue_mu + coach_mu
    mu_nudge = _clamp(mu_nudge, -cfg.max_mean_nudge_frac, cfg.max_mean_nudge_frac)

    sigma_mult = venue_sigma * coach_sigma
    sigma_mult = _clamp(sigma_mult, cfg.min_sigma_mult, cfg.max_sigma_mult)

    # Apply conservatively: mean nudge at half strength (keeps context secondary).
    mu_adj = float(mu * (1.0 + 0.5 * mu_nudge))
    sigma_adj = float(max(1e-9, sigma * sigma_mult))

    prov = _sha256(_stable_json({
        "lib_fp": lib.fingerprint(),
        "mu": float(mu),
        "sigma": float(sigma),
        "venue_id": venue_id,
        "coach_id": coach_id,
        "mu_nudge": float(mu_nudge),
        "sigma_mult": float(sigma_mult),
    }))

    return ModifierResult(
        mu_adj=mu_adj,
        sigma_adj=sigma_adj,
        mu_nudge_frac=float(mu_nudge),
        sigma_mult=float(sigma_mult),
        provenance_hash=prov,
    )


# -----------------------------
# Backtest encoding hook (simple, deterministic)
# -----------------------------

def encode_venue_record_from_backtest(
    *,
    sport: str,
    venue_id: str,
    raw_mean_delta_frac: float,
    raw_sigma_mult: float,
    cfg: Optional[ModifierConfig] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> VenueRecord:
    """
    Use this AFTER you backtest a venue effect from your dataset.
    This just clamps values into policy bounds and returns a record.
    """
    cfg = cfg or ModifierConfig()
    mean_nudge = _clamp(float(raw_mean_delta_frac), -cfg.max_mean_nudge_frac, cfg.max_mean_nudge_frac)
    sigma_mult = _clamp(float(raw_sigma_mult), cfg.min_sigma_mult, cfg.max_sigma_mult)

    return VenueRecord(
        venue_id=str(venue_id),
        sport=str(sport),
        mean_nudge_frac=float(mean_nudge),
        sigma_mult=float(sigma_mult),
        meta=meta or {},
    )
