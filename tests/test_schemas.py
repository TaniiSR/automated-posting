import pytest
from pydantic import ValidationError

from app.schemas import PostingRequest

URL = "https://example.com"


def make_message(length: int) -> str:
    """Message of exactly `length` characters containing one URL at the end."""
    filler = "x" * (length - len(URL) - 1)
    return f"{filler} {URL}"


@pytest.mark.parametrize(
    "message, expected_url",
    [
        ("Check out our platform https://example.com", "https://example.com"),
        ("Visit https://example.com.", "https://example.com"),
        ("Visit (https://example.com/a/b?x=1&y=2) now", "https://example.com/a/b?x=1&y=2"),
        ("http://example.org is live", "http://example.org"),
        ("  padded https://example.com  ", "https://example.com"),
    ],
)
def test_valid_messages_are_accepted(message, expected_url):
    request = PostingRequest(message=message)
    assert request.url == expected_url


def test_message_is_trimmed():
    assert PostingRequest(message="  hi https://example.com  ").message == "hi https://example.com"


def test_message_of_exactly_200_chars_is_accepted():
    message = make_message(200)
    assert len(message) == 200
    assert PostingRequest(message=message).message == message


def test_message_of_201_chars_is_rejected():
    message = make_message(201)
    with pytest.raises(ValidationError) as exc:
        PostingRequest(message=message)
    assert "200" in str(exc.value)


@pytest.mark.parametrize("message", ["", "   ", "\n\t"])
def test_empty_message_is_rejected(message):
    with pytest.raises(ValidationError) as exc:
        PostingRequest(message=message)
    assert "empty" in str(exc.value).lower()


def test_message_without_link_is_rejected():
    with pytest.raises(ValidationError) as exc:
        PostingRequest(message="No link in this one")
    assert "exactly one" in str(exc.value).lower()


@pytest.mark.parametrize(
    "message",
    [
        "Two links https://example.com and https://example.org",
        "Same link twice https://example.com https://example.com",
    ],
)
def test_message_with_more_than_one_link_is_rejected(message):
    with pytest.raises(ValidationError) as exc:
        PostingRequest(message=message)
    assert "exactly one" in str(exc.value).lower()


@pytest.mark.parametrize(
    "message",
    [
        "Bad scheme ftp://example.com",
        "Nothing after scheme http://",
    ],
)
def test_non_http_links_are_rejected(message):
    with pytest.raises(ValidationError):
        PostingRequest(message=message)


@pytest.mark.parametrize(
    "message",
    [
        "Local https://localhost",
        "No tld http://example",
        "Dot first http://.com",
        "Dot last http://example.",
        "No scheme www.example.com",
    ],
)
def test_malformed_urls_are_rejected(message):
    with pytest.raises(ValidationError) as exc:
        PostingRequest(message=message)
    assert "url" in str(exc.value).lower()


def test_missing_message_field_is_rejected():
    with pytest.raises(ValidationError):
        PostingRequest()


def test_non_string_message_is_rejected():
    with pytest.raises(ValidationError):
        PostingRequest(message=123)
