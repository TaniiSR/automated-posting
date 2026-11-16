import json

import httpx
import pytest

from app.platforms.base import MissingCredentials, PlatformError
from app.platforms.devto import DevTo

URL = "https://example.com"
MESSAGE = "Grow your visibility https://example.com"


class FakeDevTo:
    def __init__(self, status=201, body=None):
        self.requests = []
        self.status = status
        self.body = body if body is not None else {"url": "https://dev.to/me/grow-1a2b"}

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(self.status, json=self.body)

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(self.handler))

    def article(self):
        return json.loads(self.requests[0].content)["article"]


@pytest.fixture(autouse=True)
def credentials(monkeypatch):
    monkeypatch.setenv("DEVTO_API_KEY", "devto-key")


def test_platform_name():
    assert DevTo().name == "Dev.to"


async def test_publishes_article_with_api_key_header():
    fake = FakeDevTo()
    async with fake.client() as client:
        posted = await DevTo().post(client, MESSAGE, URL)

    request = fake.requests[0]
    assert request.method == "POST"
    assert str(request.url) == "https://dev.to/api/articles"
    assert request.headers["api-key"] == "devto-key"
    assert fake.article()["body_markdown"] == MESSAGE
    assert fake.article()["published"] is True
    assert posted.url == "https://dev.to/me/grow-1a2b"


async def test_title_is_the_message_without_the_link():
    fake = FakeDevTo()
    async with fake.client() as client:
        await DevTo().post(client, MESSAGE, URL)
    assert fake.article()["title"] == "Grow your visibility"


async def test_title_falls_back_when_message_is_only_the_link():
    fake = FakeDevTo()
    async with fake.client() as client:
        await DevTo().post(client, URL, URL)
    assert fake.article()["title"] == "New update"


async def test_title_is_limited_in_length():
    fake = FakeDevTo()
    message = "w" * 190 + " " + URL
    async with fake.client() as client:
        await DevTo().post(client, message, URL)
    assert 0 < len(fake.article()["title"]) <= 80


async def test_missing_api_key_fails_without_calling_the_api(monkeypatch):
    monkeypatch.delenv("DEVTO_API_KEY")
    fake = FakeDevTo()
    async with fake.client() as client:
        with pytest.raises(MissingCredentials, match="DEVTO_API_KEY"):
            await DevTo().post(client, MESSAGE, URL)
    assert fake.requests == []


async def test_unauthorized_raises_platform_error_with_status():
    fake = FakeDevTo(status=401, body={"error": "unauthorized"})
    async with fake.client() as client:
        with pytest.raises(PlatformError, match="HTTP 401"):
            await DevTo().post(client, MESSAGE, URL)


async def test_rate_limit_raises_platform_error_with_status():
    fake = FakeDevTo(status=429, body={"error": "Rate limit reached"})
    async with fake.client() as client:
        with pytest.raises(PlatformError, match="HTTP 429"):
            await DevTo().post(client, MESSAGE, URL)


async def test_response_without_url_raises_platform_error():
    fake = FakeDevTo(body={"id": 1})
    async with fake.client() as client:
        with pytest.raises(PlatformError, match="no article URL"):
            await DevTo().post(client, MESSAGE, URL)
