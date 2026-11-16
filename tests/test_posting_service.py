import asyncio
from datetime import datetime

import httpx
import pytest

from app.platforms.base import MissingCredentials, Platform, PlatformError, Posted
from app.services.posting_service import PostingService

MESSAGE = "Grow your visibility https://example.com"
URL = "https://example.com"
FIXED_NOW = datetime(2026, 11, 15, 10, 30, 0)


class Fake(Platform):
    def __init__(self, name, posted_url=None, error=None):
        self.name = name
        self.posted_url = posted_url
        self.error = error
        self.calls = []

    async def post(self, client, message, url):
        self.calls.append((message, url))
        if self.error:
            raise self.error
        return Posted(url=self.posted_url)


def make_client(public_urls=(), status_for_others=404):
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) in public_urls:
            return httpx.Response(200)
        if status_for_others == "error":
            raise httpx.ConnectError("unreachable")
        return httpx.Response(status_for_others)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def make_service(platforms, client):
    return PostingService(platforms, client=client, now=lambda: FIXED_NOW)


async def test_successful_platform_returns_full_result():
    platform = Fake("A", posted_url="https://a.test/1")
    async with make_client(public_urls=["https://a.test/1"]) as client:
        response = await make_service([platform], client).publish(MESSAGE, URL)

    assert response.success is True
    assert response.results[0].model_dump() == {
        "platform": "A",
        "status": "success",
        "posted_url": "https://a.test/1",
        "public_access": True,
        "date": "2026-11-15",
        "time": "10:30:00",
        "error": None,
    }


async def test_each_platform_receives_message_and_url():
    platform = Fake("A", posted_url="https://a.test/1")
    async with make_client() as client:
        await make_service([platform], client).publish(MESSAGE, URL)
    assert platform.calls == [(MESSAGE, URL)]


async def test_one_failure_does_not_stop_the_others():
    good_one = Fake("Good1", posted_url="https://g1.test/1")
    broken = Fake("Broken", error=PlatformError("HTTP 401: bad token"))
    good_two = Fake("Good2", posted_url="https://g2.test/1")
    async with make_client(public_urls=["https://g1.test/1", "https://g2.test/1"]) as client:
        response = await make_service([good_one, broken, good_two], client).publish(MESSAGE, URL)

    assert response.success is True
    assert [r.status for r in response.results] == ["success", "failed", "success"]
    assert response.results[1].error == "HTTP 401: bad token"


async def test_failed_result_has_no_url_date_time_or_public_access():
    broken = Fake("Broken", error=MissingCredentials("TOKEN"))
    async with make_client() as client:
        response = await make_service([broken], client).publish(MESSAGE, URL)

    assert response.results[0].model_dump() == {
        "platform": "Broken",
        "status": "failed",
        "posted_url": None,
        "public_access": False,
        "date": None,
        "time": None,
        "error": "Missing credentials: set TOKEN",
    }


async def test_unexpected_exception_is_captured_with_its_type():
    broken = Fake("Broken", error=RuntimeError("boom"))
    async with make_client() as client:
        response = await make_service([broken], client).publish(MESSAGE, URL)
    assert response.results[0].status == "failed"
    assert response.results[0].error == "RuntimeError: boom"


async def test_exception_with_empty_message_still_gives_useful_error():
    broken = Fake("Broken", error=httpx.ReadTimeout(""))
    async with make_client() as client:
        response = await make_service([broken], client).publish(MESSAGE, URL)
    assert response.results[0].error == "ReadTimeout"


async def test_overall_success_is_false_when_every_platform_fails():
    platforms = [Fake("A", error=PlatformError("x")), Fake("B", error=PlatformError("y"))]
    async with make_client() as client:
        response = await make_service(platforms, client).publish(MESSAGE, URL)
    assert response.success is False
    assert len(response.results) == 2


async def test_no_platforms_means_no_success():
    async with make_client() as client:
        response = await make_service([], client).publish(MESSAGE, URL)
    assert response.success is False
    assert response.results == []


async def test_public_access_false_when_posted_url_returns_404():
    platform = Fake("A", posted_url="https://a.test/1")
    async with make_client(status_for_others=404) as client:
        response = await make_service([platform], client).publish(MESSAGE, URL)
    assert response.results[0].status == "success"
    assert response.results[0].public_access is False


async def test_public_access_false_when_posted_url_is_unreachable():
    platform = Fake("A", posted_url="https://a.test/1")
    async with make_client(status_for_others="error") as client:
        response = await make_service([platform], client).publish(MESSAGE, URL)
    assert response.results[0].status == "success"
    assert response.results[0].public_access is False


async def test_platforms_run_concurrently():
    """A waits for B's signal. If they ran one after the other this would hang."""
    signal = asyncio.Event()

    class Waiter(Platform):
        name = "Waiter"

        async def post(self, client, message, url):
            await signal.wait()
            return Posted(url="https://w.test/1")

    class Signaller(Platform):
        name = "Signaller"

        async def post(self, client, message, url):
            signal.set()
            return Posted(url="https://s.test/1")

    async with make_client() as client:
        service = make_service([Waiter(), Signaller()], client)
        response = await asyncio.wait_for(service.publish(MESSAGE, URL), timeout=2)
    assert [r.status for r in response.results] == ["success", "success"]


async def test_results_keep_platform_order_even_if_they_finish_out_of_order():
    class Slow(Platform):
        name = "Slow"

        async def post(self, client, message, url):
            await asyncio.sleep(0.05)
            return Posted(url="https://slow.test/1")

    fast = Fake("Fast", posted_url="https://fast.test/1")
    async with make_client() as client:
        response = await make_service([Slow(), fast], client).publish(MESSAGE, URL)
    assert [r.platform for r in response.results] == ["Slow", "Fast"]
