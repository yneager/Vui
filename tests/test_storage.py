from autoqa.models import ScanReport
from autoqa import storage


def test_previous_completed_and_atomic_save(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DATA_DIR", tmp_path)
    storage._memory.clear()
    first = ScanReport(scan_id="first", target_url="https://x.test", status="completed", score=90)
    second = ScanReport(scan_id="second", target_url="https://x.test", status="running")
    storage.save(first)
    storage.save(second)
    baseline = storage.previous_completed("https://x.test", "second")
    assert baseline and baseline.scan_id == "first"
    assert not list(tmp_path.glob("*.tmp"))
