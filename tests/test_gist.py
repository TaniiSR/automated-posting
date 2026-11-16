import json

import httpx
import pytest

from app.platforms.base import MissingCredentials, PlatformError
from app.platforms.gist import GithubGist

URL = "https://example.com"
MESSAGE = "Grow your visibility https://example.com"


class FakeGithub:
    def __init__(self, status=201, body=None):
        self.requests = []
        self.status = status
        self.body = body if body is not None else {"html_url": "https://gist.github.com/me/abc123"}

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(self.status, json=self.body)

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(self.handler))

    def body_sent(self):
        return json.loads(self.requests[0].content)


@pytest.fixture(autouse=True)
def credentials(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "gh-token")


def test_platform_name():
    assert GithubGist().name == "GitHub Gist"


async def test_creates_public_gist_and_returns_its_url():
    fake = FakeGithub()
    async with fake.client() as client:
        posted = await GithubGist().post(client, MESSAGE, URL)

    request = fake.requests[0]
    assert request.method == "POST"
    assert str(request.url) == "https://api.github.com/gists"
    assert fake.body_sent() == {
        "description": MESSAGE,
        "public": True,
        "files": {"post.md": {"content": MESSAGE}},
    }
    assert posted.url == "https://gist.github.com/me/abc123"


async def test_sends_required_github_headers():
    fake = FakeGithub()
    async with fake.client() as client:
        await GithubGist().post(client, MESSAGE, URL)

    headers = fake.requests[0].headers
    assert headers["Authorization"] == "Bearer gh-token"
    assert headers["Accept"] == "application/vnd.github+json"
    assert headers["X-GitHub-Api-Version"] == "2022-11-28"
    assert headers["User-Agent"]


async def test_missing_token_fails_without_calling_the_api(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN")
    fake = FakeGithub()
    async with fake.client() as client:
        with pytest.raises(MissingCredentials, match="GITHUB_TOKEN"):
            await GithubGist().post(client, MESSAGE, URL)
    assert fake.requests == []


@pytest.mark.parametrize("status", [401, 403, 422])
async def test_http_errors_raise_platform_error_with_status(status):
    fake = FakeGithub(status=status, body={"message": "nope"})
    async with fake.client() as client:
        with pytest.raises(PlatformError, match=f"HTTP {status}"):
            await GithubGist().post(client, MESSAGE, URL)


async def test_response_without_html_url_raises_platform_error():
    fake = FakeGithub(body={"id": "abc123"})
    async with fake.client() as client:
        with pytest.raises(PlatformError, match="no gist URL"):
            await GithubGist().post(client, MESSAGE, URL)
