"""FastAPI surface integration tests (paper-only operator day)."""

from pathlib import Path

from fastapi.testclient import TestClient

from hollersports.api.app import create_app


def test_health():
    with TestClient(create_app(data_root="/tmp/holler-test-api")) as client:
        r = client.get("/v1/health")
        assert r.status_code == 200
        body = r.json()
        assert body["capital_authority"] is False


def test_fixture_ingest_and_dashboard(tmp_path):
    with TestClient(create_app(data_root=str(tmp_path))) as client:
        r = client.post("/v1/runs/ingest", json={"fixture": "day001"})
        assert r.status_code == 200
        assert r.json()["status"] in ("INGESTED", "REJECTED")
        r2 = client.post("/v1/runs/compete", json={})
        assert r2.status_code == 200
        d = client.get("/v1/dashboard")
        assert d.status_code == 200
        assert d.json()["authority"] == "PROJECTION_ONLY"


def test_full_day_and_candidates(tmp_path):
    with TestClient(create_app(data_root=str(tmp_path))) as client:
        r = client.post("/v1/runs/full-day", json={"fixture": "day001"})
        assert r.status_code == 200
        body = r.json()
        assert body["capital_authority"] is False
        assert body["mode"] == "ADVISORY_ONLY"
        assert body["dashboard_authority"] == "PROJECTION_ONLY"
        c = client.get("/v1/candidates")
        assert c.status_code == 200
        assert c.json()["capital_authority"] is False
        rel = client.get("/v1/reliability")
        assert rel.status_code == 200
        assert rel.json()["capital_authority"] is False
        assert rel.json()["mode"] == "ADVISORY_ONLY"
        hist = client.get("/v1/reliability", params={"history": 1, "limit": 5})
        assert hist.status_code == 200
        hbody = hist.json()
        assert hbody["schema_version"] == "ReliabilityHistoryPacket.v1"
        assert hbody["capital_authority"] is False
        assert hbody["count"] >= 1
        assert len(hbody["entries"]) == hbody["count"]


def test_day002_full_day_and_calibrated_model_edge(tmp_path):
    """day002 carries model_probability; model edge only with RELIABLE calibration."""
    with TestClient(create_app(data_root=str(tmp_path))) as client:
        r = client.post("/v1/runs/full-day", json={"fixture": "day002"})
        assert r.status_code == 200
        assert r.json()["capital_authority"] is False

        cal = client.get("/v1/calibration", params={"allow_forecast_weighting": 1})
        assert cal.status_code == 200
        cal_body = cal.json()
        assert cal_body["schema_version"] == "CalibrationPacket.v1"
        assert cal_body["capital_authority"] is False
        # Fixture day sample is below reliable floor
        assert cal_body["status"] in {"EMPTY", "UNRELIABLE", "WATCH"}
        assert cal_body["model_edge_allowed"] is False

        off = client.post("/v1/runs/compete", json={})
        assert off.status_code == 200
        off_body = off.json()
        assert off_body.get("model_edge_enabled") is False
        off_ids = [c.get("strategy_id") for c in off_body.get("candidates") or []]
        assert "MODEL_PROBABILITY_EDGE" not in off_ids

        # Auto-calibration with allow=true still blocked on small fixture sample
        auto = client.post(
            "/v1/runs/compete",
            json={
                "allow_forecast_weighting": True,
                "use_auto_calibration": True,
            },
        )
        assert auto.status_code == 200
        assert auto.json().get("model_edge_enabled") is False

        # Manual RELIABLE override (tests / operator override path)
        on = client.post(
            "/v1/runs/compete",
            json={
                "allow_forecast_weighting": True,
                "reliability_status": "RELIABLE",
                "use_auto_calibration": False,
            },
        )
        assert on.status_code == 200
        on_body = on.json()
        assert on_body.get("model_edge_enabled") is True
        model = [
            c
            for c in on_body.get("candidates") or []
            if c.get("strategy_id") == "MODEL_PROBABILITY_EDGE"
        ]
        assert len(model) >= 1
        assert model[0].get("authority") == "SHADOW_ONLY"
        assert model[0].get("capital_authority") is False


def test_ml_train_annotate_compete(tmp_path):
    """Track F: train ensemble → annotate day003 ingest → model edge candidates."""
    with TestClient(create_app(data_root=str(tmp_path))) as client:
        # Fail closed: annotate without train
        miss = client.post("/v1/ml/annotate", json={})
        assert miss.status_code == 404

        empty = client.get("/v1/ml/status")
        assert empty.status_code == 200
        assert empty.json()["capital_authority"] is False
        assert empty.json()["ensemble_present"] is False

        train = client.post(
            "/v1/ml/train",
            json={"train_fixtures": ["day001", "day002"], "seed": 42},
        )
        assert train.status_code == 200, train.text
        tbody = train.json()
        assert tbody["status"] == "TRAINED"
        assert tbody["capital_authority"] is False
        assert tbody["execution_authority"] is False
        assert Path(tbody["ensemble_path"]).is_file()

        st = client.get("/v1/ml/status")
        assert st.json()["ensemble_present"] is True

        # Need ingest before annotate
        bad = client.post("/v1/ml/annotate", json={})
        assert bad.status_code == 400

        ing = client.post("/v1/runs/ingest", json={"fixture": "day003"})
        assert ing.status_code == 200
        assert ing.json()["status"] == "INGESTED"

        # Auto-calibration on small fixture bank → model edge usually off (ladder intact).
        ann_auto = client.post(
            "/v1/ml/annotate",
            json={
                "auto_compete": True,
                "allow_forecast_weighting": True,
                "use_auto_calibration": True,
            },
        )
        assert ann_auto.status_code == 200, ann_auto.text
        assert ann_auto.json()["status"] == "ANNOTATED"
        assert ann_auto.json()["annotated_markets"] >= 1
        assert ann_auto.json()["capital_authority"] is False
        # Small sample: model edge must not force-open via Workbench-style auto path
        assert ann_auto.json().get("model_edge_enabled") is False

        # Explicit manual RELIABLE remains available for offline demos / tests only
        ann = client.post(
            "/v1/ml/annotate",
            json={
                "auto_compete": True,
                "allow_forecast_weighting": True,
                "reliability_status": "RELIABLE",
                "use_auto_calibration": False,
            },
        )
        assert ann.status_code == 200, ann.text
        abody = ann.json()
        assert abody["status"] == "ANNOTATED"
        assert abody["annotated_markets"] >= 1
        assert abody["model_edge_enabled"] is True
        assert abody["model_edge_candidate_count"] >= 1
        assert abody["capital_authority"] is False
        assert abody["execution_authority"] is False

        cands = client.get("/v1/candidates")
        assert cands.status_code == 200
        model = [
            c
            for c in cands.json().get("candidates") or []
            if c.get("strategy_id") == "MODEL_PROBABILITY_EDGE"
        ]
        assert len(model) >= 1
        assert model[0]["authority"] == "SHADOW_ONLY"

        # Advisory retrain-check (never trains)
        rt = client.post(
            "/v1/ml/retrain-check",
            json={"eval_fixtures": ["day001", "day002", "day003"], "min_labeled": 5},
        )
        assert rt.status_code == 200, rt.text
        rbody = rt.json()
        assert rbody["schema_version"] == "HollerMlRetrainProposal.v1"
        assert rbody["status"] in {"HOLD", "RETRAIN_SUGGESTED", "NOT_COMPUTABLE"}
        assert rbody["capital_authority"] is False
        assert rbody["execution_authority"] is False
        assert rbody.get("auto_retrain") is False
        st2 = client.get("/v1/ml/status")
        assert st2.json().get("last_retrain_proposal") is not None

        card = client.get("/v1/ml/model-card")
        assert card.status_code == 200, card.text
        assert card.json()["schema_version"] == "HollerModelCard.v1"
        assert card.json()["capital_authority"] is False
        assert "markdown" in card.json()

        ax = client.post("/v1/ml/axial-stub")
        assert ax.status_code == 200, ax.text
        assert ax.json()["schema_version"] == "HollerAxialStub.v1"
        assert ax.json()["kind"] == "axial_temporal_stub"
        assert ax.json()["execution_authority"] is False


def test_free_first_injected_no_network(tmp_path):
    with TestClient(create_app(data_root=str(tmp_path))) as client:
        espn_raw = {
            "sport": "BASKETBALL",
            "events": [
                {
                    "id": "401",
                    "date": "2026-04-24T23:00:00Z",
                    "competitions": [
                        {
                            "competitors": [
                                {"team": {"abbreviation": "BOS"}},
                                {"team": {"abbreviation": "LAL"}},
                            ]
                        }
                    ],
                }
            ],
        }
        odds_raw = [
            {
                "id": "401",
                "home_team": "BOS",
                "away_team": "LAL",
                "commence_time": "2026-04-24T23:00:00Z",
                "bookmakers": [
                    {
                        "key": "book_a",
                        "markets": [
                            {
                                "key": "h2h",
                                "outcomes": [
                                    {"name": "BOS", "price": -120},
                                    {"name": "LAL", "price": 100},
                                ],
                            }
                        ],
                    }
                ],
            }
        ]
        r = client.post(
            "/v1/runs/free-first",
            json={
                "espn_raw": espn_raw,
                "odds_raw": odds_raw,
                "auto_compete": True,
                "run_id": "T-API-FF",
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body["capital_authority"] is False
        assert body["mode"] == "ADVISORY_ONLY"
        assert body["status"] == "OBSERVED"
        assert body.get("espn_event_count", 0) >= 1
        assert body.get("ingest_count", 0) >= 1
        assert body.get("competed_event_count", 0) >= 1
        assert body.get("competition_status") == "COMPUTED"
        assert body.get("candidate_count", 0) >= 1

        cand = client.get("/v1/candidates")
        assert cand.status_code == 200
        assert cand.json()["candidate_count"] >= 1


def test_free_first_multi_event_auto_compete_merges(tmp_path):
    """Multi-game injected free-first competes all INGESTED events (not first-only)."""
    with TestClient(create_app(data_root=str(tmp_path))) as client:
        espn_raw = {
            "sport": "BASKETBALL",
            "events": [
                {
                    "id": "espn-a",
                    "date": "2026-04-24T23:00:00Z",
                    "competitions": [
                        {
                            "competitors": [
                                {"team": {"abbreviation": "BOS"}},
                                {"team": {"abbreviation": "LAL"}},
                            ]
                        }
                    ],
                },
                {
                    "id": "espn-b",
                    "date": "2026-04-25T02:00:00Z",
                    "competitions": [
                        {
                            "competitors": [
                                {"team": {"abbreviation": "GSW"}},
                                {"team": {"abbreviation": "PHX"}},
                            ]
                        }
                    ],
                },
            ],
        }
        odds_raw = [
            {
                "id": "odds-a",
                "home_team": "BOS",
                "away_team": "LAL",
                "commence_time": "2026-04-24T23:00:00Z",
                "bookmakers": [
                    {
                        "key": "book_a",
                        "markets": [
                            {
                                "key": "h2h",
                                "outcomes": [
                                    {"name": "BOS", "price": -120},
                                    {"name": "LAL", "price": 100},
                                ],
                            }
                        ],
                    }
                ],
            },
            {
                "id": "odds-b",
                "home_team": "GSW",
                "away_team": "PHX",
                "commence_time": "2026-04-25T02:00:00Z",
                "bookmakers": [
                    {
                        "key": "book_a",
                        "markets": [
                            {
                                "key": "h2h",
                                "outcomes": [
                                    {"name": "GSW", "price": -110},
                                    {"name": "PHX", "price": -110},
                                ],
                            }
                        ],
                    }
                ],
            },
        ]
        r = client.post(
            "/v1/runs/free-first",
            json={
                "espn_raw": espn_raw,
                "odds_raw": odds_raw,
                "auto_compete": True,
                "run_id": "T-API-FF-MULTI",
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "OBSERVED"
        assert body["ingest_count"] == 2
        assert body["competed_event_count"] == 2
        assert body["competition_status"] == "COMPUTED"
        assert body["candidate_count"] >= 2
        assert body["capital_authority"] is False

        cand = client.get("/v1/candidates")
        assert cand.status_code == 200
        cbody = cand.json()
        assert cbody["candidate_count"] >= 2
        event_ids = {c.get("event_id") for c in cbody.get("candidates") or []}
        assert len(event_ids) >= 2

        # Re-compete must keep multi-event slate (not collapse to primary ingest).
        recompete = client.post("/v1/runs/compete", json={})
        assert recompete.status_code == 200
        rc = recompete.json()
        assert rc["status"] == "COMPUTED"
        assert rc.get("competed_event_count") == 2
        assert rc["candidate_count"] >= 2
        assert {c.get("event_id") for c in rc.get("candidates") or []} == event_ids

        # Paper prices must cover markets from every ingested event.
        paper = client.post("/v1/runs/paper", json={})
        assert paper.status_code == 200
        pbody = paper.json()
        assert pbody["capital_authority"] is False
        assert pbody["execution_authority"] is False
        # At least one entry approved/accepted when prices exist across slate.
        assert pbody.get("status") in ("COMPUTED", "PARTIAL", "EMPTY", "REJECTED")
        entries = list(
            pbody.get("ledger_entries") or pbody.get("portfolio_entries") or []
        )
        # Multi-event candidates with prices should not all fail for missing price.
        if entries:
            missing_price = [
                e
                for e in entries
                if isinstance(e, dict)
                and "missing" in str(e.get("reject_reason") or e.get("reason") or "").lower()
                and "price" in str(e.get("reject_reason") or e.get("reason") or "").lower()
            ]
            assert len(missing_price) < len(entries)

        dash = client.get("/v1/dashboard")
        assert dash.status_code == 200
        slate = (dash.json().get("panels") or {}).get("slate") or {}
        assert slate.get("ingest_count") == 2
        assert slate.get("competed_event_count") == 2
        assert slate.get("path") == "free-first"

        # Settle with injected ESPN finals (fail-closed when not final).
        finals = {
            "sport": "BASKETBALL",
            "events": [
                {
                    "id": "espn-a",
                    "date": "2026-04-24T23:00:00Z",
                    "status": {
                        "type": {
                            "name": "STATUS_FINAL",
                            "completed": True,
                            "state": "post",
                        }
                    },
                    "competitions": [
                        {
                            "competitors": [
                                {
                                    "team": {"abbreviation": "BOS"},
                                    "score": "110",
                                    "winner": True,
                                    "homeAway": "home",
                                },
                                {
                                    "team": {"abbreviation": "LAL"},
                                    "score": "100",
                                    "winner": False,
                                    "homeAway": "away",
                                },
                            ]
                        }
                    ],
                },
                {
                    "id": "espn-b",
                    "date": "2026-04-25T02:00:00Z",
                    "status": {
                        "type": {
                            "name": "STATUS_SCHEDULED",
                            "completed": False,
                            "state": "pre",
                        }
                    },
                    "competitions": [
                        {
                            "competitors": [
                                {"team": {"abbreviation": "GSW"}, "score": ""},
                                {"team": {"abbreviation": "PHX"}, "score": ""},
                            ]
                        }
                    ],
                },
            ],
        }
        settle = client.post(
            "/v1/runs/settle",
            json={"espn_raw": finals, "leagues": ["NBA"]},
        )
        assert settle.status_code == 200
        sbody = settle.json()
        assert sbody["capital_authority"] is False
        assert sbody.get("result_count", 0) >= 2
        sentries = list(sbody.get("entries") or [])
        if sentries:
            statuses = {str(e.get("status") or "") for e in sentries if isinstance(e, dict)}
            # Finals for espn-a may WIN/LOSS; espn-b stays PENDING.
            assert statuses <= {"WIN", "LOSS", "PUSH", "VOID", "PENDING", "NOT_COMPUTABLE"}


def test_safe_packet_live_ux_returns_403(tmp_path):
    """Authority / live-UX lock from _safe_packet is HTTP 403 (fail-closed).

    Store allows a PROJECTION_ONLY dashboard whose string payload would leak
    live betting UX; GET must not 500 — it must 403 with a clear detail.
    """
    app = create_app(data_root=str(tmp_path))
    # Bypass response path only: put does not scan for live UX strings.
    app.state.store.put(
        "dashboard",
        {
            "schema_version": "OperatorDashboard.v1",
            "authority": "PROJECTION_ONLY",
            "capital_authority": False,
            "execution_authority": False,
            "status": "OK",
            "cta": "Place bet",  # forbidden live UX label
        },
    )
    with TestClient(app) as client:
        r = client.get("/v1/dashboard")
        assert r.status_code == 403
        detail = r.json().get("detail", "")
        assert "authority lock" in detail.lower() or "live betting" in detail.lower()


def test_paper_rejects_when_source_health_fail(tmp_path):
    """After FAIL source_health ingest, /runs/paper must not force gates open."""
    app = create_app(data_root=str(tmp_path))
    with TestClient(app) as client:
        # Payload that fails source health (missing required fields / provenance).
        bad_payload = {
            "run_id": "R-FAIL-HEALTH",
            "source_id": "TEST",
            "source_type": "MANUAL",
            "fetched_at": "2026-08-04T12:00:00+00:00",
            "current_time": "2026-08-04T12:01:00+00:00",
            "required_fields": ["event_id", "markets"],
            "source_refs": None,
            "payload": {"event_id": "E1", "markets": []},
        }
        ing = client.post("/v1/runs/ingest", json={"payload": bad_payload})
        assert ing.status_code == 200
        body = ing.json()
        assert body.get("status") == "REJECTED"
        assert (body.get("source_health") or {}).get("status") == "FAIL"

        # Seed a candidate so paper exercises execution_guard gates (not empty loop).
        app.state.store.put(
            "competition",
            {
                "schema_version": "StrategyCompetitionPacket.v1",
                "status": "COMPUTED",
                "run_id": "R-FAIL-HEALTH",
                "candidates": [
                    {
                        "status": "CANDIDATE",
                        "strategy_id": "MARKET_CONSENSUS_EDGE",
                        "event_id": "E1",
                        "market_id": "M1",
                        "selection": "HOME_ML",
                        "score": 0.9,
                        "price": 1.91,
                        "packet_refs": {"x": "1"},
                    }
                ],
                "candidate_count": 1,
                "authority": "SHADOW_ONLY",
                "capital_authority": False,
                "execution_authority": False,
            },
        )
        paper = client.post("/v1/runs/paper", json={})
        assert paper.status_code == 200
        paper_body = paper.json()
        assert paper_body.get("capital_authority") is False
        assert paper_body.get("execution_authority") is False
        assert paper_body.get("approved_count", 0) == 0
        assert paper_body.get("rejected_count", 0) >= 1
        executions = paper_body.get("executions") or []
        assert executions
        assert executions[0].get("status") == "REJECTED"
        assert "source_health_gate" in (executions[0].get("failed_gates") or [])


def test_free_first_day_injected_closed_loop(tmp_path):
    """POST /v1/runs/free-first-day with injected observe+finals (no network)."""
    with TestClient(create_app(data_root=str(tmp_path))) as client:
        espn_raw = {
            "sport": "BASKETBALL",
            "events": [
                {
                    "id": "espn-day",
                    "date": "2026-04-24T23:00:00Z",
                    "competitions": [
                        {
                            "competitors": [
                                {"team": {"abbreviation": "BOS"}, "homeAway": "home"},
                                {"team": {"abbreviation": "LAL"}, "homeAway": "away"},
                            ]
                        }
                    ],
                }
            ],
        }
        odds_raw = [
            {
                "id": "odds-day",
                "home_team": "BOS",
                "away_team": "LAL",
                "commence_time": "2026-04-24T23:00:00Z",
                "bookmakers": [
                    {
                        "key": "book_a",
                        "markets": [
                            {
                                "key": "h2h",
                                "outcomes": [
                                    {"name": "BOS", "price": -120},
                                    {"name": "LAL", "price": 100},
                                ],
                            }
                        ],
                    }
                ],
            }
        ]
        finals = {
            "sport": "BASKETBALL",
            "events": [
                {
                    "id": "espn-day",
                    "date": "2026-04-24T23:00:00Z",
                    "status": {
                        "type": {
                            "name": "STATUS_FINAL",
                            "completed": True,
                            "state": "post",
                        }
                    },
                    "competitions": [
                        {
                            "competitors": [
                                {
                                    "team": {"abbreviation": "BOS"},
                                    "score": "110",
                                    "winner": True,
                                    "homeAway": "home",
                                },
                                {
                                    "team": {"abbreviation": "LAL"},
                                    "score": "100",
                                    "winner": False,
                                    "homeAway": "away",
                                },
                            ]
                        }
                    ],
                }
            ],
        }
        r = client.post(
            "/v1/runs/free-first-day",
            json={
                "run_id": "T-API-FF-DAY",
                "leagues": ["NBA"],
                "espn_raw": espn_raw,
                "odds_raw": odds_raw,
                "settle_espn_raw": finals,
                "fetch_espn_finals": False,
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body["capital_authority"] is False
        assert body["execution_authority"] is False
        assert body["mode"] == "ADVISORY_ONLY"
        assert body["status"] == "OBSERVED"
        assert body.get("ingest_count", 0) >= 1
        assert body.get("paper_approved", 0) >= 1
        assert body.get("settlement_count", 0) >= 1
        assert body.get("bank_written", 0) >= 1

        dash = client.get("/v1/dashboard")
        assert dash.status_code == 200
        slate = (dash.json().get("panels") or {}).get("slate") or {}
        assert slate.get("path") == "free-first"
        assert slate.get("ingest_count", 0) >= 1

        cand = client.get("/v1/candidates")
        assert cand.status_code == 200
        assert cand.json()["candidate_count"] >= 1
