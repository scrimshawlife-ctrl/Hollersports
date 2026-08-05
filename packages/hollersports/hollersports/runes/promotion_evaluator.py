"""Promotion evaluator: performance + evidence → PromotionPacket.v1.

Defaults from design §8.2. Never authorizes live execution.
"""

from __future__ import annotations

from typing import Any, Mapping

from hollersports.governance.authority import Authority, assert_no_live_capital
from hollersports.schemas.packets import PromotionPacket

# Design §8.2 promotion gates (config-tunable defaults).
MIN_SAMPLE_SIZE = 100
MIN_ROI = 0.05
MAX_DRAWDOWN = 0.20
MIN_CLV_RETENTION = 0.0
MIN_SOURCE_HEALTH_PASS_RATE = 0.95
MIN_REGIMES = 3
MIN_MARKET_TYPES = 3


def evaluate_promotion(
    performance: Mapping[str, Any] | dict[str, Any] | None,
    evidence: Mapping[str, Any] | dict[str, Any] | None,
) -> dict[str, Any]:
    """Evaluate promotion readiness from performance metrics and evidence.

    Statuses: BLOCKED | WATCH | REVIEW_ELIGIBLE | PROMOTION_RECOMMENDED.
    Always SHADOW_ONLY; never grants capital or execution authority.
    """
    perf: Mapping[str, Any] = performance if isinstance(performance, Mapping) else {}
    evid: Mapping[str, Any] = evidence if isinstance(evidence, Mapping) else {}

    sample_size = float(perf.get("sample_size") or 0)
    roi = float(perf.get("roi") or 0.0)
    max_drawdown = float(perf.get("max_drawdown") or 0.0)
    clv_retention = float(perf.get("clv_retention") or 0.0)

    source_health_pass_rate = float(evid.get("source_health_pass_rate") or 0.0)
    invariance_pass = bool(evid.get("invariance_pass"))
    regimes = int(evid.get("regimes") or 0)
    market_types = int(evid.get("market_types") or 0)
    unresolved_blockers = int(evid.get("unresolved_blockers") or 0)

    target_id = str(evid.get("target_id") or perf.get("portfolio_id") or "default")
    target_type = str(evid.get("target_type") or "PORTFOLIO")
    if target_type not in {
        "STRATEGY",
        "EDGE_FAMILY",
        "EXECUTION_POLICY",
        "PORTFOLIO",
    }:
        target_type = "PORTFOLIO"

    gates: list[tuple[str, bool]] = [
        ("sample_size", sample_size >= MIN_SAMPLE_SIZE),
        ("roi", roi > MIN_ROI),
        ("max_drawdown", max_drawdown < MAX_DRAWDOWN),
        ("clv_retention", clv_retention >= MIN_CLV_RETENTION),
        (
            "source_health_pass_rate",
            source_health_pass_rate >= MIN_SOURCE_HEALTH_PASS_RATE,
        ),
        ("invariance_pass", invariance_pass),
        ("regimes", regimes >= MIN_REGIMES),
        ("market_types", market_types >= MIN_MARKET_TYPES),
        ("unresolved_blockers", unresolved_blockers == 0),
    ]

    passed_gates = [name for name, ok in gates if ok]
    failed_gates = [name for name, ok in gates if not ok]

    if failed_gates:
        # Any hard failure keeps promotion blocked (esp. small sample).
        status = "BLOCKED"
        reason = "failed_gates:" + ",".join(failed_gates)
    else:
        status = "PROMOTION_RECOMMENDED"
        reason = "all_gates_passed"

    packet = PromotionPacket(
        status=status,  # type: ignore[arg-type]
        target_id=target_id,
        target_type=target_type,  # type: ignore[arg-type]
        passed_gates=passed_gates,
        failed_gates=failed_gates,
        evidence_refs={
            "sample_size": sample_size,
            "roi": roi,
            "max_drawdown": max_drawdown,
            "clv_retention": clv_retention,
            "source_health_pass_rate": source_health_pass_rate,
            "invariance_pass": invariance_pass,
            "regimes": regimes,
            "market_types": market_types,
            "unresolved_blockers": unresolved_blockers,
        },
        authority=Authority.SHADOW_ONLY.value,
        capital_authority=False,
        execution_authority=False,
        reason=reason,
        provenance={"defaults": "design_§8.2"},
    )
    out = packet.model_dump()
    assert_no_live_capital(out)
    return out
