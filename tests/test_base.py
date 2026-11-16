import httpx
import pytest

from app.platforms.base import MissingCredentials, Platform, PlatformError, Posted, check


def test_missing_credentials_is_a_platform_error():
    assert issubclass(MissingCredentials, PlatformError)


def test_missing_credentials_lists_every_name():
    error = MissingCredentials("BLUESKY_HANDLE", "BLUESKY_APP_PASSWORD")
    assert str(error) == "Missing credentials: set BLUESKY_HANDLE, BLUESKY_APP_PASSWORD"


def test_missing_credentials_with_single_name():
    assert str(MissingCredentials("DEVTO_API_KEY")) == "Missing credentials: set DEVTO_API_KEY"


@pytest.mark.parametrize("status", [200, 201])
def test_check_returns_response_for_success_codes(status):
    response = httpx.Response(status, text="ok")
    assert check(response) is response


def test_check_raises_for_error_status_with_code_and_body():
    response = httpx.Response(401, text="bad token")
    with pytest.raises(PlatformError) as exc:
        check(response)
    assert str(exc.value) == "HTTP 401: bad token"


def test_check_truncates_long_bodies_and_flattens_newlines():
    response = httpx.Response(500, text="line1\n" + "x" * 500)
    with pytest.raises(PlatformError) as exc:
        check(response)
    message = str(exc.value)
    assert "\n" not in message
    assert len(message) <= len("HTTP 500: ") + 200


def test_check_accepts_custom_success_codes():
    response = httpx.Response(204)
    assert check(response, ok=(204,)) is response
    with pytest.raises(PlatformError):
        check(httpx.Response(200), ok=(204,))


def test_posted_holds_url():
    assert Posted(url="https://example.com/p/1").url == "https://example.com/p/1"


def test_platform_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        Platform()


async def test_concrete_platform_can_post():
    class Fake(Platform):
        name = "Fake"

        async def post(self, client, message, url):
            return Posted(url="https://fake.test/1")

    async with httpx.AsyncClient() as client:
        posted = await Fake().post(client, "hi https://example.com", "https://example.com")
    assert posted.url == "https://fake.test/1"
