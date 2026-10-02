from uuid import uuid4

from fastapi.testclient import TestClient

from autoqa.app import app
from autoqa.models import ScanReport
from autoqa.storage import save

client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["version"] == "1.1.0"


def test_private_target_rejected():
    r = client.post("/api/scans", json={"target_url": "http://10.0.0.1", "max_pages": 1})
    assert r.status_code == 400


def test_fake_local_demo_on_other_port_is_rejected():
    r = client.post("/api/scans", json={"target_url": "http://127.0.0.1:9999/demo/en", "max_pages": 1})
    assert r.status_code == 400


def test_index_and_demo_are_served():
    assert client.get("/").status_code == 200
    assert "AutoQA UAE" in client.get("/").text
    demo = client.get("/demo/en")
    assert demo.status_code == 200
    assert "AUTOQA_SEEDED_JS_ERROR" in demo.text


def test_report_exports():
    scan_id = uuid4().hex
    report = ScanReport(scan_id=scan_id, target_url="https://example.com", status="completed", score=92)
    save(report)
    j = client.get(f"/api/scans/{scan_id}/export.json")
    h = client.get(f"/api/scans/{scan_id}/export.html")
    assert j.status_code == 200 and j.headers["content-type"].startswith("application/json")
    assert h.status_code == 200 and "AutoQA UAE report" in h.text
