from urllib.parse import parse_qs

import httpx
import pytest

from app.platforms.base import MissingCredentials, PlatformError
from app.platforms.pastebin import Pastebin

URL = "https://example.com"
MESSAGE = "Grow your visibility https://example.com"
PASTE_URL = "https://pastebin.com/AbC123xy"


class FakePastebin:
    """Pastebin answers with plain text, and reports errors as text with HTTP 200."""

    def __init__(self, text=PASTE_URL, status=200):
        self.requests = []
        self.text = text
        self.status = status

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(self.status, text=self.text)

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(self.handler))

    def form(self):
        return {k: v[0] for k, v in parse_qs(self.requests[0].content.decode()).items()}


@pytest.fixture(autouse=True)
def credentials(monkeypatch):
    monkeypatch.setenv("PASTEBIN_API_KEY", "paste-key")


def test_platform_name():
    assert Pastebin().name == "Pastebin"


async def test_creates_public_paste_and_returns_its_url():
    fake = FakePastebin()
    async with fake.client() as client:
        posted = await Pastebin().post(client, MESSAGE, URL)

    request = fake.requests[0]
    assert request.method == "POST"
    assert str(request.url) == "https://pastebin.com/api/api_post.php"
    assert fake.form() == {
        "api_dev_key": "paste-key",
        "api_option": "paste",
        "api_paste_code": MESSAGE,
        "api_paste_name": "Grow your visibility",
        "api_paste_private": "0",
        "api_paste_expire_date": "N",
    }
    assert posted.url == PASTE_URL


async def test_surrounding_whitespace_in_the_response_is_ignored():
    fake = FakePastebin(text=f"  {PASTE_URL}\n")
    async with fake.client() as client:
        posted = await Pastebin().post(client, MESSAGE, URL)
    assert posted.url == PASTE_URL


async def test_missing_key_fails_without_calling_the_api(monkeypatch):
    monkeypatch.delenv("PASTEBIN_API_KEY")
    fake = FakePastebin()
    async with fake.client() as client:
        with pytest.raises(MissingCredentials, match="PASTEBIN_API_KEY"):
            await Pastebin().post(client, MESSAGE, URL)
    assert fake.requests == []


@pytest.mark.parametrize(
    "text",
    [
        "Bad API request, invalid api_dev_key",
        "Bad API request, you can't create public pastes",
        "Post limit, maximum pastes per 24h reached",
        "",
    ],
)
async def test_error_text_with_http_200_is_a_failure_not_a_success(text):
    fake = FakePastebin(text=text)
    async with fake.client() as client:
        with pytest.raises(PlatformError, match="Pastebin"):
            await Pastebin().post(client, MESSAGE, URL)


async def test_error_message_includes_what_pastebin_said():
    fake = FakePastebin(text="Bad API request, invalid api_dev_key")
    async with fake.client() as client:
        with pytest.raises(PlatformError, match="invalid api_dev_key"):
            await Pastebin().post(client, MESSAGE, URL)


async def test_http_error_raises_platform_error_with_status():
    fake = FakePastebin(text="server error", status=500)
    async with fake.client() as client:
        with pytest.raises(PlatformError, match="HTTP 500"):
            await Pastebin().post(client, MESSAGE, URL)
