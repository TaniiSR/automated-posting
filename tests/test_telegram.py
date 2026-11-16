import json

import httpx
import pytest

from app.platforms.base import MissingCredentials, PlatformError
from app.platforms.telegram import Telegram

URL = "https://example.com"
MESSAGE = "Grow your visibility https://example.com"
OK_BODY = {"ok": True, "result": {"message_id": 42, "chat": {"username": "mychannel"}}}


class FakeTelegram:
    def __init__(self, status=200, body=None):
        self.requests = []
        self.status = status
        self.body = body if body is not None else OK_BODY

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(self.status, json=self.body)

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(self.handler))

    def body_sent(self):
        return json.loads(self.requests[0].content)


@pytest.fixture(autouse=True)
def credentials(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "@mychannel")


def test_platform_name():
    assert Telegram().name == "Telegram"


async def test_sends_message_to_the_channel_and_returns_its_public_link():
    fake = FakeTelegram()
    async with fake.client() as client:
        posted = await Telegram().post(client, MESSAGE, URL)

    request = fake.requests[0]
    assert request.method == "POST"
    assert str(request.url) == "https://api.telegram.org/bot123:abc/sendMessage"
    assert fake.body_sent() == {"chat_id": "@mychannel", "text": MESSAGE}
    assert posted.url == "https://t.me/mychannel/42"


async def test_falls_back_to_chat_id_username_when_response_has_none():
    fake = FakeTelegram(body={"ok": True, "result": {"message_id": 7, "chat": {}}})
    async with fake.client() as client:
        posted = await Telegram().post(client, MESSAGE, URL)
    assert posted.url == "https://t.me/mychannel/7"


async def test_private_chat_without_username_is_reported_as_not_public(monkeypatch):
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "-1001234567890")
    fake = FakeTelegram(body={"ok": True, "result": {"message_id": 7, "chat": {}}})
    async with fake.client() as client:
        with pytest.raises(PlatformError, match="public"):
            await Telegram().post(client, MESSAGE, URL)


@pytest.mark.parametrize("missing", ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"])
async def test_missing_credential_fails_without_calling_the_api(monkeypatch, missing):
    monkeypatch.delenv(missing)
    fake = FakeTelegram()
    async with fake.client() as client:
        with pytest.raises(MissingCredentials, match="TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID"):
            await Telegram().post(client, MESSAGE, URL)
    assert fake.requests == []


async def test_http_error_raises_platform_error_with_status():
    fake = FakeTelegram(status=401, body={"ok": False, "description": "Unauthorized"})
    async with fake.client() as client:
        with pytest.raises(PlatformError, match="HTTP 401"):
            await Telegram().post(client, MESSAGE, URL)


async def test_ok_false_in_a_200_response_raises_platform_error():
    fake = FakeTelegram(body={"ok": False, "description": "chat not found"})
    async with fake.client() as client:
        with pytest.raises(PlatformError, match="chat not found"):
            await Telegram().post(client, MESSAGE, URL)


async def test_response_without_message_id_raises_platform_error():
    fake = FakeTelegram(body={"ok": True, "result": {"chat": {"username": "mychannel"}}})
    async with fake.client() as client:
        with pytest.raises(PlatformError, match="message_id"):
            await Telegram().post(client, MESSAGE, URL)
