"""FastAPI surface integration tests (paper-only operator day)."""

from fastapi.testclient import TestClient

from hollersports.api.app import create_app


def test_health():
    client = TestClient(create_app(data_root="/tmp/holler-test-api"))
    r = client.get("/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["capital_authority"] is False


def test_fixture_ingest_and_dashboard(tmp_path):
    client = TestClient(create_app(data_root=str(tmp_path)))
    r = client.post("/v1/runs/ingest", json={"fixture": "day001"})
    assert r.status_code == 200
    assert r.json()["status"] in ("INGESTED", "REJECTED")
    r2 = client.post("/v1/runs/compete", json={})
    assert r2.status_code == 200
    d = client.get("/v1/dashboard")
    assert d.status_code == 200
    assert d.json()["authority"] == "PROJECTION_ONLY"


def test_full_day_and_candidates(tmp_path):
    client = TestClient(create_app(data_root=str(tmp_path)))
    r = client.post("/v1/runs/full-day", json={"fixture": "day001"})
    assert r.status_code == 200
    body = r.json()
    assert body["capital_authority"] is False
    assert body["mode"] == "ADVISORY_ONLY"
    assert body["dashboard_authority"] == "PROJECTION_ONLY"
    c = client.get("/v1/candidates")
    assert c.status_code == 200
    assert c.json()["capital_authority"] is False
