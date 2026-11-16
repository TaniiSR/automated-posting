import json
from urllib.parse import parse_qs

import httpx
import pytest

from app.platforms.base import PlatformError
from app.platforms.telegraph import Telegraph

URL = "https://example.com"
MESSAGE = "Grow your visibility https://example.com today"


class FakeTelegraph:
    """Records requests and answers like the Telegraph API."""

    def __init__(self, account=None, page=None, status=200):
        self.requests = []
        self.account = account or {"ok": True, "result": {"access_token": "anon-token"}}
        self.page = page or {"ok": True, "result": {"url": "https://telegra.ph/Post-11-15"}}
        self.status = status

    def handler(self, request: httpx.Request) -> httpx.Response:
        form = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
        self.requests.append((request.url.path, form))
        if self.status != 200:
            return httpx.Response(self.status, text="server exploded")
        body = self.account if request.url.path == "/createAccount" else self.page
        return httpx.Response(200, json=body)

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(self.handler))

    def paths(self):
        return [path for path, _ in self.requests]


@pytest.fixture(autouse=True)
def no_token(monkeypatch):
    monkeypatch.delenv("TELEGRAPH_TOKEN", raising=False)


def test_platform_name():
    assert Telegraph().name == "Telegraph"


async def test_creates_anonymous_account_when_no_token_set():
    fake = FakeTelegraph()
    async with fake.client() as client:
        posted = await Telegraph().post(client, MESSAGE, URL)

    assert fake.paths() == ["/createAccount", "/createPage"]
    assert fake.requests[1][1]["access_token"] == "anon-token"
    assert posted.url == "https://telegra.ph/Post-11-15"


async def test_uses_configured_token_without_creating_account(monkeypatch):
    monkeypatch.setenv("TELEGRAPH_TOKEN", "my-token")
    fake = FakeTelegraph()
    async with fake.client() as client:
        await Telegraph().post(client, MESSAGE, URL)

    assert fake.paths() == ["/createPage"]
    assert fake.requests[0][1]["access_token"] == "my-token"


async def test_page_content_makes_the_link_clickable():
    fake = FakeTelegraph()
    async with fake.client() as client:
        await Telegraph().post(client, MESSAGE, URL)

    content = json.loads(fake.requests[1][1]["content"])
    assert content == [
        {
            "tag": "p",
            "children": [
                "Grow your visibility ",
                {"tag": "a", "attrs": {"href": URL}, "children": [URL]},
                " today",
            ],
        }
    ]


async def test_message_that_is_only_the_link_has_no_empty_text_nodes():
    fake = FakeTelegraph()
    async with fake.client() as client:
        await Telegraph().post(client, URL, URL)

    content = json.loads(fake.requests[1][1]["content"])
    assert content[0]["children"] == [{"tag": "a", "attrs": {"href": URL}, "children": [URL]}]


async def test_title_is_never_empty_and_within_limit():
    fake = FakeTelegraph()
    long_message = "y" * 190 + " " + URL
    async with fake.client() as client:
        await Telegraph().post(client, long_message, URL)

    title = fake.requests[1][1]["title"]
    assert 0 < len(title) <= 256


async def test_api_error_on_create_page_raises_platform_error():
    fake = FakeTelegraph(page={"ok": False, "error": "ACCESS_TOKEN_INVALID"})
    async with fake.client() as client:
        with pytest.raises(PlatformError, match="ACCESS_TOKEN_INVALID"):
            await Telegraph().post(client, MESSAGE, URL)


async def test_api_error_on_create_account_raises_platform_error():
    fake = FakeTelegraph(account={"ok": False, "error": "SHORT_NAME_REQUIRED"})
    async with fake.client() as client:
        with pytest.raises(PlatformError, match="SHORT_NAME_REQUIRED"):
            await Telegraph().post(client, MESSAGE, URL)
    assert fake.paths() == ["/createAccount"]


async def test_http_error_raises_platform_error_with_status():
    fake = FakeTelegraph(status=500)
    async with fake.client() as client:
        with pytest.raises(PlatformError, match="HTTP 500"):
            await Telegraph().post(client, MESSAGE, URL)
