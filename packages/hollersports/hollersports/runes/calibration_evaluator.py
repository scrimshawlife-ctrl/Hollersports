"""Advice-quality calibration evaluator (no money, no live books).

Derives RELIABLE / WATCH / UNRELIABLE from settled paper outcomes so model-edge
and operators can gate forecast weighting on evidence, not vibes.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from hollersports.governance.authority import Authority, assert_no_live_capital
from hollersports.schemas.hashing import packet_hash

_SETTLED = frozenset({"WIN", "LOSS", "PUSH", "VOID"})

# Defaults: tunable via evaluate_calibration kwargs / thresholds dict.
DEFAULT_MIN_SAMPLE_WATCH = 5
DEFAULT_MIN_SAMPLE_RELIABLE = 20
DEFAULT_MIN_HIT_RATE_RELIABLE = 0.45
DEFAULT_MIN_SIM_ROI_RELIABLE = -0.15


def _settled_rows(
    settled_entries: Sequence[Mapping[str, Any]] | None,
) -> list[dict[str, Any]]:
    return [
        dict(e)
        for e in (settled_entries or [])
        if isinstance(e, Mapping) and str(e.get("status") or "").upper() in _SETTLED
    ]


def _metrics(rows: list[dict[str, Any]]) -> dict[str, float | int]:
    n = len(rows)
    if n == 0:
        return {"sample_size": 0, "hit_rate": 0.0, "sim_roi": 0.0, "wins": 0}
    wins = sum(1 for r in rows if str(r.get("status") or "").upper() == "WIN")
    stakes = [float(r.get("stake") or r.get("paper_stake") or 0.0) for r in rows]
    pnls = [float(r.get("pnl") or r.get("settled_value") or 0.0) for r in rows]
    stake_sum = sum(stakes) or 0.0
    pnl_sum = sum(pnls)
    return {
        "sample_size": n,
        "wins": wins,
        "hit_rate": round(wins / n, 4),
        "sim_roi": round(pnl_sum / stake_sum, 4) if stake_sum else 0.0,
    }


def evaluate_calibration(
    settled_entries: Sequence[Mapping[str, Any]] | None,
    *,
    allow_forecast_weighting: bool = False,
    min_sample_watch: int = DEFAULT_MIN_SAMPLE_WATCH,
    min_sample_reliable: int = DEFAULT_MIN_SAMPLE_RELIABLE,
    min_hit_rate_reliable: float = DEFAULT_MIN_HIT_RATE_RELIABLE,
    min_sim_roi_reliable: float = DEFAULT_MIN_SIM_ROI_RELIABLE,
) -> dict[str, Any]:
    """Compute CalibrationPacket.v1 from settled paper entries.

    Status ladder (advice quality only):
      EMPTY → no settled sample
      UNRELIABLE → sample below watch floor or metrics fail reliable floors
      WATCH → enough for watch but not reliable
      RELIABLE → sample + hit_rate + sim_roi pass reliable floors

    ``model_edge_allowed`` requires RELIABLE and ``allow_forecast_weighting``.
    Never grants capital or execution authority.
    """
    rows = _settled_rows(settled_entries)
    metrics = _metrics(rows)
    sample_size = int(metrics["sample_size"])
    hit_rate = float(metrics["hit_rate"])
    sim_roi = float(metrics["sim_roi"])

    thresholds = {
        "min_sample_watch": int(min_sample_watch),
        "min_sample_reliable": int(min_sample_reliable),
        "min_hit_rate_reliable": float(min_hit_rate_reliable),
        "min_sim_roi_reliable": float(min_sim_roi_reliable),
    }

    gates: list[tuple[str, bool]] = []
    if sample_size == 0:
        status = "EMPTY"
        gates = [
            ("has_settled_sample", False),
        ]
    else:
        gate_defs = [
            ("sample_watch", sample_size >= thresholds["min_sample_watch"]),
            ("sample_reliable", sample_size >= thresholds["min_sample_reliable"]),
            ("hit_rate_reliable", hit_rate >= thresholds["min_hit_rate_reliable"]),
            ("sim_roi_floor", sim_roi >= thresholds["min_sim_roi_reliable"]),
        ]
        gates = gate_defs
        by_name = {n: ok for n, ok in gate_defs}
        if (
            by_name["sample_reliable"]
            and by_name["hit_rate_reliable"]
            and by_name["sim_roi_floor"]
        ):
            status = "RELIABLE"
        elif by_name["sample_watch"]:
            status = "WATCH"
        else:
            status = "UNRELIABLE"

    passed = [n for n, ok in gates if ok]
    failed = [n for n, ok in gates if not ok]

    # Gate-compatible field: EMPTY treated as UNRELIABLE for model edge.
    reliability_status = "RELIABLE" if status == "RELIABLE" else (
        "WATCH" if status == "WATCH" else "UNRELIABLE"
    )
    allow = bool(allow_forecast_weighting)
    model_edge_allowed = allow and reliability_status == "RELIABLE"

    packet: dict[str, Any] = {
        "schema_version": "CalibrationPacket.v1",
        "status": status,
        "reliability_status": reliability_status,
        "allow_forecast_weighting": allow,
        "model_edge_allowed": model_edge_allowed,
        "sample_size": sample_size,
        "hit_rate": hit_rate,
        "sim_roi": sim_roi,
        "passed_gates": passed,
        "failed_gates": failed,
        "thresholds": thresholds,
        "authority": Authority.SHADOW_ONLY.value,
        "capital_authority": False,
        "execution_authority": False,
        "mode": "ADVISORY_ONLY",
        "provenance": {
            "purpose": "advice_quality_calibration",
            "real_money": False,
            "note": "simulation_metrics_only",
        },
    }
    packet["packet_hash"] = packet_hash(
        {k: v for k, v in packet.items() if k != "packet_hash"}
    )
    assert_no_live_capital(packet)
    return packet


def calibration_gate_from_packet(
    packet: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Shrink CalibrationPacket (or partial dict) to competition gate fields."""
    if not packet:
        return {
            "allow_forecast_weighting": False,
            "reliability_status": "UNRELIABLE",
        }
    return {
        "allow_forecast_weighting": bool(packet.get("allow_forecast_weighting")),
        "reliability_status": str(
            packet.get("reliability_status") or packet.get("status") or "UNRELIABLE"
        ),
    }
