"""Axial temporal stub — research placeholder (no PyTorch required).

Inspired by axial transformer factorizations (arXiv 2511.18730) but **not** a
neural net: applies deterministic per-axis smoothing over a feature sequence
so operators can wire minute-level tensors later without inventing odds.

Interface is stable; a real axial model can replace ``score_sequence`` later
behind the same packet contract.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from hollersports.schemas.hashing import packet_hash


def _mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def smooth_temporal_axis(
    sequence: Sequence[Sequence[float]],
    *,
    window: int = 3,
) -> list[list[float]]:
    """Causal moving average along time (axis 0). Fail soft on short sequences."""
    if not sequence:
        return []
    w = max(1, int(window))
    n_t = len(sequence)
    n_f = len(sequence[0])
    out: list[list[float]] = []
    for t in range(n_t):
        start = max(0, t - w + 1)
        slice_rows = sequence[start : t + 1]
        row: list[float] = []
        for j in range(n_f):
            vals = []
            for r in slice_rows:
                if j < len(r):
                    try:
                        vals.append(float(r[j]))
                    except (TypeError, ValueError):
                        continue
            row.append(_mean(vals) if vals else 0.0)
        out.append(row)
    return out


def smooth_feature_axis(
    sequence: Sequence[Sequence[float]],
    *,
    blend: float = 0.25,
) -> list[list[float]]:
    """Blend each feature toward per-timestep mean (pseudo feature-axis mix)."""
    b = max(0.0, min(1.0, float(blend)))
    out: list[list[float]] = []
    for row in sequence:
        vals = []
        for v in row:
            try:
                vals.append(float(v))
            except (TypeError, ValueError):
                vals.append(0.0)
        m = _mean(vals)
        out.append([(1.0 - b) * v + b * m for v in vals])
    return out


def score_sequence(
    sequence: Sequence[Sequence[float]],
    *,
    window: int = 3,
    feature_blend: float = 0.25,
) -> dict[str, Any]:
    """Run axial-style dual-axis smooth and emit last-step summary.

    Returns packet with ``last_features``, per-step norms, and provenance.
    Does not produce betting recommendations.
    """
    if not sequence:
        return {
            "schema_version": "HollerAxialStub.v1",
            "status": "NOT_COMPUTABLE",
            "reason": "empty_sequence",
            "capital_authority": False,
            "execution_authority": False,
            "authority": "SHADOW_ONLY",
            "mode": "ADVISORY_ONLY",
            "kind": "axial_temporal_stub",
        }
    # Normalize ragged rows
    width = max(len(r) for r in sequence)
    normed: list[list[float]] = []
    for r in sequence:
        row = []
        for j in range(width):
            if j < len(r):
                try:
                    row.append(float(r[j]))
                except (TypeError, ValueError):
                    row.append(0.0)
            else:
                row.append(0.0)
        normed.append(row)

    t_smooth = smooth_temporal_axis(normed, window=window)
    f_smooth = smooth_feature_axis(t_smooth, blend=feature_blend)
    last = f_smooth[-1]
    step_norms = [sum(abs(x) for x in row) / max(1, len(row)) for row in f_smooth]
    packet = {
        "schema_version": "HollerAxialStub.v1",
        "status": "COMPUTED",
        "kind": "axial_temporal_stub",
        "seq_len": len(f_smooth),
        "n_features": width,
        "window": int(window),
        "feature_blend": float(feature_blend),
        "last_features": last,
        "step_l1_mean": step_norms,
        "terminal_l1_mean": step_norms[-1] if step_norms else 0.0,
        "note": "stdlib_stub_not_neural_axial_transformer",
        "capital_authority": False,
        "execution_authority": False,
        "authority": "SHADOW_ONLY",
        "mode": "ADVISORY_ONLY",
    }
    packet["packet_hash"] = packet_hash(
        {k: v for k, v in packet.items() if k != "packet_hash"}
    )
    return packet


def markets_to_sequence(
    markets: Sequence[Mapping[str, Any]],
    feature_keys: Sequence[str] | None = None,
) -> list[list[float]]:
    """Build a pseudo time sequence from markets (stable sort by market_id).

    Uses numeric fields only; missing → 0. For true minute-level tensors, callers
    should pass ordered slices instead.
    """
    keys = list(
        feature_keys
        or (
            "implied_probability",
            "consensus_score",
            "public_bet_pct",
            "handle_pct",
            "clv_retention",
            "odds_delta",
            "sentiment_score",
        )
    )
    ordered = sorted(
        [m for m in markets if isinstance(m, Mapping)],
        key=lambda m: str(m.get("market_id") or ""),
    )
    seq: list[list[float]] = []
    for m in ordered:
        row: list[float] = []
        for k in keys:
            raw = m.get(k)
            if raw is None and k == "implied_probability":
                raw = m.get("market_implied_probability")
            try:
                row.append(float(raw) if raw is not None else 0.0)
            except (TypeError, ValueError):
                row.append(0.0)
        seq.append(row)
    return seq
