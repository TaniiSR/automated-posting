import json
from datetime import datetime

import httpx
import pytest

from app.platforms.base import MissingCredentials, PlatformError
from app.platforms.bluesky import Bluesky

URL = "https://example.com"
MESSAGE = "Grow your visibility https://example.com today"
DID = "did:plc:abc123"
SESSION = {"accessJwt": "jwt-token", "did": DID}
RECORD = {"uri": f"at://{DID}/app.bsky.feed.post/3kxyz", "cid": "bafy"}


class FakeBluesky:
    def __init__(self, session=None, record=None, session_status=200, record_status=200):
        self.requests = []
        self.session = SESSION if session is None else session
        self.record = RECORD if record is None else record
        self.session_status = session_status
        self.record_status = record_status

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.url.path.endswith("createSession"):
            return httpx.Response(self.session_status, json=self.session)
        return httpx.Response(self.record_status, json=self.record)

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(self.handler))

    def paths(self):
        return [r.url.path for r in self.requests]

    def body(self, index):
        return json.loads(self.requests[index].content)


@pytest.fixture(autouse=True)
def credentials(monkeypatch):
    monkeypatch.setenv("BLUESKY_HANDLE", "me.bsky.social")
    monkeypatch.setenv("BLUESKY_APP_PASSWORD", "app-pass")


def test_platform_name():
    assert Bluesky().name == "Bluesky"


async def test_logs_in_then_creates_post_and_returns_public_url():
    fake = FakeBluesky()
    async with fake.client() as client:
        posted = await Bluesky().post(client, MESSAGE, URL)

    assert fake.paths() == [
        "/xrpc/com.atproto.server.createSession",
        "/xrpc/com.atproto.repo.createRecord",
    ]
    assert fake.body(0) == {"identifier": "me.bsky.social", "password": "app-pass"}
    assert posted.url == f"https://bsky.app/profile/{DID}/post/3kxyz"


async def test_create_record_uses_session_token_and_post_collection():
    fake = FakeBluesky()
    async with fake.client() as client:
        await Bluesky().post(client, MESSAGE, URL)

    request = fake.requests[1]
    assert request.headers["Authorization"] == "Bearer jwt-token"
    body = fake.body(1)
    assert body["repo"] == DID
    assert body["collection"] == "app.bsky.feed.post"
    assert body["record"]["$type"] == "app.bsky.feed.post"
    assert body["record"]["text"] == MESSAGE


async def test_created_at_is_utc_iso_timestamp():
    fake = FakeBluesky()
    async with fake.client() as client:
        await Bluesky().post(client, MESSAGE, URL)

    created_at = fake.body(1)["record"]["createdAt"]
    assert created_at.endswith("Z")
    datetime.fromisoformat(created_at.replace("Z", "+00:00"))


async def test_link_facet_points_at_the_url_by_byte_offsets():
    fake = FakeBluesky()
    async with fake.client() as client:
        await Bluesky().post(client, MESSAGE, URL)

    facet = fake.body(1)["record"]["facets"][0]
    start, end = facet["index"]["byteStart"], facet["index"]["byteEnd"]
    assert MESSAGE.encode()[start:end] == URL.encode()
    assert facet["features"] == [{"$type": "app.bsky.richtext.facet#link", "uri": URL}]


async def test_facet_offsets_count_bytes_not_characters():
    message = "Café 🚀 launch https://example.com"
    fake = FakeBluesky()
    async with fake.client() as client:
        await Bluesky().post(client, message, URL)

    facet = fake.body(1)["record"]["facets"][0]
    start, end = facet["index"]["byteStart"], facet["index"]["byteEnd"]
    assert message.encode("utf-8")[start:end] == URL.encode()
    assert start != message.find(URL)  # would be equal if counting characters


@pytest.mark.parametrize("missing", ["BLUESKY_HANDLE", "BLUESKY_APP_PASSWORD"])
async def test_missing_credential_fails_without_calling_the_api(monkeypatch, missing):
    monkeypatch.delenv(missing)
    fake = FakeBluesky()
    async with fake.client() as client:
        with pytest.raises(MissingCredentials, match="BLUESKY_HANDLE, BLUESKY_APP_PASSWORD"):
            await Bluesky().post(client, MESSAGE, URL)
    assert fake.requests == []


async def test_login_failure_stops_before_posting():
    fake = FakeBluesky(session={"error": "AuthenticationRequired"}, session_status=401)
    async with fake.client() as client:
        with pytest.raises(PlatformError, match="HTTP 401"):
            await Bluesky().post(client, MESSAGE, URL)
    assert fake.paths() == ["/xrpc/com.atproto.server.createSession"]


async def test_create_record_failure_raises_platform_error():
    fake = FakeBluesky(record={"error": "InvalidRequest"}, record_status=400)
    async with fake.client() as client:
        with pytest.raises(PlatformError, match="HTTP 400"):
            await Bluesky().post(client, MESSAGE, URL)


@pytest.mark.parametrize("session", [{"did": DID}, {"accessJwt": "jwt-token"}])
async def test_incomplete_session_response_raises_platform_error(session):
    fake = FakeBluesky(session=session)
    async with fake.client() as client:
        with pytest.raises(PlatformError, match="session"):
            await Bluesky().post(client, MESSAGE, URL)


async def test_record_response_without_uri_raises_platform_error():
    fake = FakeBluesky(record={"cid": "bafy"})
    async with fake.client() as client:
        with pytest.raises(PlatformError, match="uri"):
            await Bluesky().post(client, MESSAGE, URL)
