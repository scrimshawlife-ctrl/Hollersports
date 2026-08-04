"""Pydantic models mirroring schemas/json/*.v1.schema.json packet contracts."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from hollersports.governance.authority import Authority


class PacketBase(BaseModel):
    """Shared governance fields for all v1 packets."""

    model_config = ConfigDict(extra="allow")

    capital_authority: bool = False
    execution_authority: bool = False
    provenance: dict[str, Any] = Field(default_factory=dict)

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        # Omit unset optionals (e.g. reason=None) so JSON Schema string fields stay valid.
        kwargs.setdefault("exclude_none", True)
        return super().model_dump(**kwargs)


class SourceHealthPacket(PacketBase):
    schema_version: Literal["SourceHealthPacket.v1"] = "SourceHealthPacket.v1"
    status: Literal["PASS", "WARN", "FAIL", "NOT_COMPUTABLE"]
    source_id: str
    freshness_seconds: float = 0
    missing_required_fields: list[str] = Field(default_factory=list)
    stale: bool = False
    provenance_present: bool = False
    health_score: float = 0.0
    authority: str = Authority.SHADOW_ONLY.value
    reason: str | None = None


class MarketIngestionPacket(PacketBase):
    schema_version: Literal["MarketIngestionPacket.v1"] = "MarketIngestionPacket.v1"
    status: Literal["INGESTED", "REJECTED", "NOT_COMPUTABLE"]
    run_id: str
    source_id: str = "UNKNOWN"
    source_type: Literal["ESPN", "ODDS_FEED", "MANUAL", "FIXTURE", "UNKNOWN"] = "UNKNOWN"
    fetched_at: str = ""
    event_id: str = "UNKNOWN"
    sport: str = "UNKNOWN"
    league: str = "UNKNOWN"
    teams: list[str] = Field(default_factory=list)
    markets: list[dict[str, Any]] = Field(default_factory=list)
    source_refs: dict[str, Any] = Field(default_factory=dict)
    source_health: dict[str, Any] | None = None
    authority: str = Authority.SHADOW_ONLY.value
    reason: str | None = None


class StrategyCandidatePacket(PacketBase):
    schema_version: Literal["StrategyCandidatePacket.v1"] = "StrategyCandidatePacket.v1"
    status: Literal["CANDIDATE", "REJECTED", "NOT_COMPUTABLE"]
    run_id: str
    strategy_id: str
    strategy_family: str = ""
    event_id: str
    market_id: str
    selection: str
    score: float = 0.0
    confidence: float = 0.0
    features: dict[str, Any] = Field(default_factory=dict)
    packet_refs: dict[str, Any] = Field(default_factory=dict)
    authority: str = Authority.SHADOW_ONLY.value
    reason: str | None = None


class ExecutionPacket(PacketBase):
    schema_version: Literal["ExecutionPacket.v1"] = "ExecutionPacket.v1"
    status: Literal[
        "APPROVED_FOR_PAPER",
        "REJECTED",
        "BLOCKED",
        "MANUAL_REVIEW",
        "LIVE_APPROVED",
        "NOT_COMPUTABLE",
    ]
    run_id: str
    candidate_id: str = ""
    event_id: str = ""
    market_id: str = ""
    selection: str = ""
    price: float = 0.0
    point: float | None = None
    sportsbook: str = ""
    stake: float = 0.0
    # v1: LIVE_APPROVED is not constructible; assert_no_live_capital is defense-in-depth.
    mode: Literal["PAPER_ONLY", "MANUAL_REVIEW", "LIVE_DISABLED"] = "PAPER_ONLY"
    passed_gates: list[str] = Field(default_factory=list)
    failed_gates: list[str] = Field(default_factory=list)
    packet_refs: dict[str, Any] = Field(default_factory=dict)
    expected_value: float = 0.0
    authority: str = Authority.SHADOW_FIRST.value
    reason: str | None = None


class PaperPortfolioPacket(PacketBase):
    schema_version: Literal["PaperPortfolioPacket.v1"] = "PaperPortfolioPacket.v1"
    status: Literal["RECORDED", "NOT_COMPUTABLE"]
    run_id: str
    portfolio_id: str
    entry_id: str = ""
    starting_bankroll: float = 0.0
    paper_stake: float = 0.0
    paper_result: Literal[
        "PENDING", "WIN", "LOSS", "PUSH", "VOID", "NOT_COMPUTABLE"
    ] = "PENDING"
    expected_value: float = 0.0
    settled_value: float | None = None
    event_id: str = ""
    market_id: str = ""
    selection: str = ""
    price: float = 0.0
    packet_refs: dict[str, Any] = Field(default_factory=dict)
    authority: str = Authority.SHADOW_ONLY.value
    reason: str | None = None


class SettlementPacket(PacketBase):
    schema_version: Literal["SettlementPacket.v1"] = "SettlementPacket.v1"
    status: Literal["PENDING", "WIN", "LOSS", "PUSH", "VOID", "NOT_COMPUTABLE"]
    entry_id: str = ""
    run_id: str = ""
    portfolio_id: str = ""
    event_id: str = ""
    market_id: str = ""
    selection: str = ""
    stake: float = 0.0
    price: float = 0.0
    pnl: float = 0.0
    final_score: str | None = None
    result_source: str = ""
    settled_at: str = ""
    authority: str = Authority.SHADOW_ONLY.value
    reason: str | None = None


class PerformancePacket(PacketBase):
    schema_version: Literal["PerformancePacket.v1"] = "PerformancePacket.v1"
    status: Literal["INFERRED", "NOT_COMPUTABLE"]
    portfolio_id: str = ""
    sample_size: float = 0
    roi: float = 0.0
    hit_rate: float = 0.0
    clv_retention: float = 0.0
    max_drawdown: float = 0.0
    volatility: float = 0.0
    sharpe_like_ratio: float = 0.0
    profit_factor: float = 0.0
    average_stake: float = 0.0
    average_expected_value: float = 0.0
    average_settled_value: float = 0.0
    by_strategy: dict[str, Any] = Field(default_factory=dict)
    by_league: dict[str, Any] = Field(default_factory=dict)
    authority: str = Authority.SHADOW_ONLY.value
    reason: str | None = None


class PromotionPacket(PacketBase):
    schema_version: Literal["PromotionPacket.v1"] = "PromotionPacket.v1"
    status: Literal[
        "BLOCKED",
        "WATCH",
        "REVIEW_ELIGIBLE",
        "PROMOTION_RECOMMENDED",
        "NOT_COMPUTABLE",
    ]
    target_id: str = ""
    target_type: Literal[
        "STRATEGY", "EDGE_FAMILY", "EXECUTION_POLICY", "PORTFOLIO"
    ] = "PORTFOLIO"
    passed_gates: list[str] = Field(default_factory=list)
    failed_gates: list[str] = Field(default_factory=list)
    evidence_refs: dict[str, Any] = Field(default_factory=dict)
    authority: str = Authority.SHADOW_ONLY.value
    reason: str | None = None


class OperatorDashboardPacket(PacketBase):
    schema_version: Literal["OperatorDashboardPacket.v1"] = (
        "OperatorDashboardPacket.v1"
    )
    status: Literal["PROJECTED", "NOT_COMPUTABLE"]
    run_id: str = ""
    portfolio_id: str = ""
    panels: dict[str, Any] = Field(default_factory=dict)
    authority: str = Authority.PROJECTION_ONLY.value
    reason: str | None = None
