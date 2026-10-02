from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from pydantic import BaseModel, Field

Severity = Literal["critical", "high", "medium", "low", "info"]
Status = Literal["queued", "running", "completed", "failed", "canceled"]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ScanRequest(BaseModel):
    target_url: str = Field(min_length=4, max_length=2048)
    max_pages: int = Field(default=8, ge=1, le=30)
    mobile_check: bool = True
    bilingual_parity: bool = True
    safe_interactions: bool = True


class Issue(BaseModel):
    id: str
    category: str
    severity: Severity
    title: str
    description: str
    page_url: str
    evidence: dict[str, Any] = Field(default_factory=dict)
    recommendation: str = ""
    viewport: str = "desktop"


class PageResult(BaseModel):
    url: str
    status_code: int | None = None
    title: str = ""
    lang: str = ""
    direction: str = ""
    load_ms: int = 0
    dom_content_loaded_ms: int | None = None
    load_event_ms: int | None = None
    dom_elements: int = 0
    resource_count: int = 0
    transfer_kb: int = 0
    links_found: int = 0
    console_errors: int = 0
    request_failures: int = 0
    safe_interactions_tested: int = 0
    navigation_error: str | None = None


class ScanReport(BaseModel):
    scan_id: str
    target_url: str
    status: Status = "queued"
    created_at: str = Field(default_factory=utc_now)
    started_at: str | None = None
    finished_at: str | None = None
    duration_ms: int | None = None
    score: int | None = None
    pages_scanned: int = 0
    issues: list[Issue] = Field(default_factory=list)
    pages: list[PageResult] = Field(default_factory=list)
    parity_pairs_checked: int = 0
    error: str | None = None
    progress_message: str = "Queued"
    options: dict[str, Any] = Field(default_factory=dict)
    baseline_scan_id: str | None = None
    new_issue_ids: list[str] = Field(default_factory=list)
    resolved_issue_ids: list[str] = Field(default_factory=list)
    unchanged_issue_ids: list[str] = Field(default_factory=list)
