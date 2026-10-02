from fastapi.testclient import TestClient
from autoqa.app import app

client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_private_target_rejected():
    r = client.post("/api/scans", json={"target_url": "http://10.0.0.1", "max_pages": 1})
    assert r.status_code == 400


def test_index_and_demo_are_served():
    assert client.get("/").status_code == 200
    assert "AutoQA UAE" in client.get("/").text
    demo = client.get("/demo/en")
    assert demo.status_code == 200
    assert "AUTOQA_SEEDED_JS_ERROR" in demo.text
