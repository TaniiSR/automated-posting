from urllib.parse import parse_qs

import httpx
import pytest

from app.platforms.base import MissingCredentials, PlatformError
from app.platforms.mastodon import Mastodon

URL = "https://example.com"
MESSAGE = "Grow your visibility https://example.com"


class FakeMastodon:
    def __init__(self, status=200, body=None):
        self.requests = []
        self.status = status
        self.body = body if body is not None else {"url": "https://mastodon.social/@me/111"}

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(self.status, json=self.body)

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(self.handler))

    def form(self):
        return {k: v[0] for k, v in parse_qs(self.requests[0].content.decode()).items()}


@pytest.fixture(autouse=True)
def credentials(monkeypatch):
    monkeypatch.setenv("MASTODON_ACCESS_TOKEN", "secret-token")
    monkeypatch.delenv("MASTODON_INSTANCE", raising=False)


def test_platform_name():
    assert Mastodon().name == "Mastodon"


async def test_posts_public_status_with_bearer_token():
    fake = FakeMastodon()
    async with fake.client() as client:
        posted = await Mastodon().post(client, MESSAGE, URL)

    request = fake.requests[0]
    assert request.method == "POST"
    assert str(request.url) == "https://mastodon.social/api/v1/statuses"
    assert request.headers["Authorization"] == "Bearer secret-token"
    assert fake.form() == {"status": MESSAGE, "visibility": "public"}
    assert posted.url == "https://mastodon.social/@me/111"


async def test_uses_custom_instance_and_ignores_trailing_slash(monkeypatch):
    monkeypatch.setenv("MASTODON_INSTANCE", "https://fosstodon.org/")
    fake = FakeMastodon()
    async with fake.client() as client:
        await Mastodon().post(client, MESSAGE, URL)
    assert str(fake.requests[0].url) == "https://fosstodon.org/api/v1/statuses"


async def test_missing_token_fails_without_calling_the_api(monkeypatch):
    monkeypatch.delenv("MASTODON_ACCESS_TOKEN")
    fake = FakeMastodon()
    async with fake.client() as client:
        with pytest.raises(MissingCredentials, match="MASTODON_ACCESS_TOKEN"):
            await Mastodon().post(client, MESSAGE, URL)
    assert fake.requests == []


async def test_http_error_raises_platform_error_with_status():
    fake = FakeMastodon(status=401, body={"error": "The access token is invalid"})
    async with fake.client() as client:
        with pytest.raises(PlatformError, match="HTTP 401"):
            await Mastodon().post(client, MESSAGE, URL)


async def test_response_without_url_raises_platform_error():
    fake = FakeMastodon(body={"id": "111"})
    async with fake.client() as client:
        with pytest.raises(PlatformError, match="no post URL"):
            await Mastodon().post(client, MESSAGE, URL)
