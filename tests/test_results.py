import pytest
from pydantic import ValidationError

from app.schemas import PlatformResult, PostingResponse


def test_success_result_matches_spec_shape():
    result = PlatformResult(
        platform="Platform A",
        status="success",
        posted_url="https://example.com/post/123",
        public_access=True,
        date="2026-11-15",
        time="10:30:00",
    )
    assert result.model_dump() == {
        "platform": "Platform A",
        "status": "success",
        "posted_url": "https://example.com/post/123",
        "public_access": True,
        "date": "2026-11-15",
        "time": "10:30:00",
        "error": None,
    }


def test_failed_result_defaults():
    result = PlatformResult(platform="Platform B", status="failed", error="Authentication failed")
    assert result.model_dump() == {
        "platform": "Platform B",
        "status": "failed",
        "posted_url": None,
        "public_access": False,
        "date": None,
        "time": None,
        "error": "Authentication failed",
    }


def test_status_must_be_success_or_failed():
    with pytest.raises(ValidationError):
        PlatformResult(platform="X", status="pending")


def test_platform_and_status_are_required():
    with pytest.raises(ValidationError):
        PlatformResult(platform="X")
    with pytest.raises(ValidationError):
        PlatformResult(status="failed")


def test_posting_response_shape():
    ok = PlatformResult(platform="A", status="success", posted_url="https://a.test/1")
    bad = PlatformResult(platform="B", status="failed", error="boom")
    response = PostingResponse(success=True, results=[ok, bad])
    dumped = response.model_dump()
    assert list(dumped) == ["success", "results"]
    assert [r["platform"] for r in dumped["results"]] == ["A", "B"]
