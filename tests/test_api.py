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


def test_health_route_reports_up():
    with TestClient(app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "up"}


def test_model_info_route_returns_metrics_and_thresholds():
    with TestClient(app) as client:
        resp = client.get("/api/model/info")
        assert resp.status_code == 200
        body = resp.json()

    for key in ("trained_on", "n_rows", "n_train", "n_test", "pr_auc", "roc_auc", "thresholds"):
        assert key in body
    assert body["n_train"] + body["n_test"] == body["n_rows"]
    assert 0.0 <= body["pr_auc"] <= 1.0
    assert 0.0 <= body["roc_auc"] <= 1.0
    thresholds = body["thresholds"]
    assert 0.0 < thresholds["medium"] < thresholds["high"] < 1.0


def test_examples_route_returns_scorable_addresses():
    import re

    from app.schemas import ADDRESS_PATTERN

    with TestClient(app) as client:
        resp = client.get("/api/examples")
        assert resp.status_code == 200
        examples = resp.json()["examples"]
        assert len(examples) == 3
        for address in examples:
            assert re.fullmatch(ADDRESS_PATTERN, address)
            scored = client.post("/api/score", json={"address": address})
            assert scored.status_code == 200
            assert scored.json()["address"] == address.lower()


def test_index_page_is_served_as_html():
    with TestClient(app) as client:
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "ChainGuard" in resp.text


def test_score_without_body_is_422():
    with TestClient(app) as client:
        assert client.post("/api/score").status_code == 422
        assert client.post("/api/score", json={}).status_code == 422


def test_unknown_api_route_returns_json_404():
    with TestClient(app) as client:
        resp = client.get("/api/nope")
        assert resp.status_code == 404
        assert isinstance(resp.json(), dict)


def test_score_response_schema_is_complete():
    with TestClient(app) as client:
        address = client.get("/api/examples").json()["examples"][0]
        body = client.post("/api/score", json={"address": address}).json()

    assert body["address"] == address.lower()
    assert isinstance(body["disclaimer"], str) and body["disclaimer"]
    assert set(body["activity"]) == {"sent", "received", "unique_counterparties", "lifetime_days"}
    assert all(isinstance(v, int) and v >= 0 for v in body["activity"].values())
    for reason in body["top_reasons"]:
        assert set(reason) == {"fact", "weight", "direction"}
        assert isinstance(reason["fact"], str) and reason["fact"]
        assert isinstance(reason["weight"], float)
        assert reason["direction"] in ("raises", "lowers")


def test_risk_band_matches_model_thresholds():
    with TestClient(app) as client:
        thresholds = client.get("/api/model/info").json()["thresholds"]
        for address in client.get("/api/examples").json()["examples"]:
            body = client.post("/api/score", json={"address": address}).json()
            score, band = body["risk_score"], body["risk_band"]
            expected = "high" if score >= thresholds["high"] else "medium" if score >= thresholds["medium"] else "low"
            assert band == expected


def test_address_matching_is_case_insensitive():
    with TestClient(app) as client:
        address = client.get("/api/examples").json()["examples"][0]
        upper = "0x" + address[2:].upper()
        resp = client.post("/api/score", json={"address": upper})
        assert resp.status_code == 200
        assert resp.json()["risk_score"] == client.post("/api/score", json={"address": address}).json()["risk_score"]


def test_malformed_address_prefix_is_422():
    with TestClient(app) as client:
        for bad in ("0X" + "a" * 40, "0x" + "a" * 39, "0x" + "g" * 40, ""):
            resp = client.post("/api/score", json={"address": bad})
            assert resp.status_code == 422, bad
            assert "message" in resp.json() and "hint" in resp.json()


def test_examples_are_deterministic():
    with TestClient(app) as client:
        assert client.get("/api/examples").json() == client.get("/api/examples").json()


def test_missing_static_file_is_404():
    with TestClient(app) as client:
        assert client.get("/no-such-file.js").status_code == 404
