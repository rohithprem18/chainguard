"""Three tests: a valid score, garbage input, a valid-but-unknown address."""

from fastapi.testclient import TestClient

from app.main import app


def test_valid_address_returns_score_with_three_reasons():
    with TestClient(app) as client:
        info = client.get("/api/examples").json()
        address = info["examples"][0]

        resp = client.post("/api/score", json={"address": address})
        assert resp.status_code == 200

        body = resp.json()
        assert 0.0 <= body["risk_score"] <= 1.0
        assert body["risk_band"] in ("low", "medium", "high")
        assert len(body["top_reasons"]) == 3


def test_garbage_address_returns_422():
    with TestClient(app) as client:
        resp = client.post("/api/score", json={"address": "not-an-address"})
        assert resp.status_code == 422
        assert "message" in resp.json()
        assert "hint" in resp.json()


def test_valid_but_unknown_address_returns_404():
    with TestClient(app) as client:
        resp = client.post(
            "/api/score", json={"address": "0x000000000000000000000000000000000000dead"}
        )
        assert resp.status_code == 404
        assert "message" in resp.json()
        assert "hint" in resp.json()
