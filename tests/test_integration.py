from datetime import datetime

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app, get_service
from app.platforms.registry import all_platforms
from app.services.posting_service import PostingService

MESSAGE = "Grow your visibility https://example.com"

ENV = {
    "MASTODON_ACCESS_TOKEN": "m-token",
    "BLUESKY_HANDLE": "me.bsky.social",
    "BLUESKY_APP_PASSWORD": "b-pass",
    "DEVTO_API_KEY": "d-key",
    "GITHUB_TOKEN": "g-token",
    "PASTEBIN_API_KEY": "p-key",
}

POSTED = {
    "Telegraph": "https://telegra.ph/p-11-15",
    "Mastodon": "https://mastodon.social/@me/1",
    "Bluesky": "https://bsky.app/profile/did:plc:x/post/3k",
    "Dev.to": "https://dev.to/me/p",
    "GitHub Gist": "https://gist.github.com/me/g",
    "Pastebin": "https://pastebin.com/AbC123xy",
}


def fake_internet(failing_hosts=(), dead_posts=()):
    """One transport that answers like all six APIs, plus the public-access check."""

    def handler(request: httpx.Request) -> httpx.Response:
        host, path = request.url.host, request.url.path
        if request.method == "GET":
            return httpx.Response(404 if str(request.url) in dead_posts else 200)
        if host in failing_hosts:
            return httpx.Response(500, text="server error")
        if host == "api.telegra.ph":
            result = (
                {"access_token": "anon"} if path == "/createAccount" else {"url": POSTED["Telegraph"]}
            )
            return httpx.Response(200, json={"ok": True, "result": result})
        if host == "mastodon.social":
            return httpx.Response(200, json={"url": POSTED["Mastodon"]})
        if host == "bsky.social":
            if path.endswith("createSession"):
                return httpx.Response(200, json={"accessJwt": "j", "did": "did:plc:x"})
            return httpx.Response(200, json={"uri": "at://did:plc:x/app.bsky.feed.post/3k"})
        if host == "dev.to":
            return httpx.Response(201, json={"url": POSTED["Dev.to"]})
        if host == "api.github.com":
            return httpx.Response(201, json={"html_url": POSTED["GitHub Gist"]})
        if host == "pastebin.com":
            return httpx.Response(200, text=POSTED["Pastebin"])
        return httpx.Response(418)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def use_service(client):
    service = PostingService(
        all_platforms(), client=client, now=lambda: datetime(2026, 11, 15, 10, 30, 0)
    )
    app.dependency_overrides[get_service] = lambda: service


@pytest.fixture(autouse=True)
def cleanup():
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def full_credentials(monkeypatch):
    for key, value in ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("TELEGRAPH_TOKEN", raising=False)


@pytest.fixture
def no_credentials(monkeypatch):
    for key in ENV:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.delenv("TELEGRAPH_TOKEN", raising=False)


def test_all_six_platforms_post_successfully(full_credentials):
    use_service(fake_internet())
    response = TestClient(app).post("/posting", json={"message": MESSAGE})

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert [r["platform"] for r in body["results"]] == list(POSTED)
    for result in body["results"]:
        assert result["status"] == "success"
        assert result["posted_url"] == POSTED[result["platform"]]
        assert result["public_access"] is True
        assert result["date"] == "2026-11-15"
        assert result["time"] == "10:30:00"
        assert result["error"] is None


def test_failing_platforms_do_not_stop_the_rest(full_credentials):
    use_service(fake_internet(failing_hosts={"dev.to", "api.github.com"}))
    results = TestClient(app).post("/posting", json={"message": MESSAGE}).json()["results"]

    by_name = {r["platform"]: r for r in results}
    assert by_name["Dev.to"]["status"] == "failed"
    assert "HTTP 500" in by_name["Dev.to"]["error"]
    assert by_name["GitHub Gist"]["status"] == "failed"
    for name in ("Telegraph", "Mastodon", "Bluesky", "Pastebin"):
        assert by_name[name]["status"] == "success"


def test_with_no_credentials_only_telegraph_posts(no_credentials):
    use_service(fake_internet())
    body = TestClient(app).post("/posting", json={"message": MESSAGE}).json()

    by_name = {r["platform"]: r for r in body["results"]}
    assert body["success"] is True
    assert by_name["Telegraph"]["status"] == "success"
    for name in ("Mastodon", "Bluesky", "Dev.to", "GitHub Gist", "Pastebin"):
        assert by_name[name]["status"] == "failed"
        assert by_name[name]["error"].startswith("Missing credentials")


def test_unreachable_post_is_reported_as_not_public(full_credentials):
    use_service(fake_internet(dead_posts={POSTED["Mastodon"]}))
    results = TestClient(app).post("/posting", json={"message": MESSAGE}).json()["results"]

    by_name = {r["platform"]: r for r in results}
    assert by_name["Mastodon"]["status"] == "success"
    assert by_name["Mastodon"]["public_access"] is False
    assert by_name["Telegraph"]["public_access"] is True


def test_invalid_message_never_reaches_any_platform(full_credentials):
    use_service(fake_internet())
    response = TestClient(app).post("/posting", json={"message": "no link here"})
    assert response.status_code == 422
