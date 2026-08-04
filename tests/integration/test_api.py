"""FastAPI surface integration tests (paper-only operator day)."""

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
