import re
from typing import Literal, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, field_validator

MAX_LENGTH = 200
URL_PATTERN = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
TRAILING_PUNCTUATION = ".,;:!?)\"'"


def extract_urls(message: str) -> list[str]:
    return [url.rstrip(TRAILING_PUNCTUATION) for url in URL_PATTERN.findall(message)]


def is_valid_url(url: str) -> bool:
    parsed = urlparse(url)
    host = parsed.hostname or ""
    return (
        parsed.scheme in ("http", "https")
        and "." in host
        and not host.startswith(".")
        and not host.endswith(".")
    )


class PostingRequest(BaseModel):
    message: str

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Message must not be empty.")
        if len(value) > MAX_LENGTH:
            raise ValueError(f"Message must not exceed {MAX_LENGTH} characters (got {len(value)}).")
        urls = extract_urls(value)
        if len(urls) != 1:
            raise ValueError(f"Message must contain exactly one CTA link (found {len(urls)}).")
        if not is_valid_url(urls[0]):
            raise ValueError(f"Invalid CTA URL: {urls[0]!r}. Use a full http(s) URL.")
        return value

    @property
    def url(self) -> str:
        return extract_urls(self.message)[0]


class PlatformResult(BaseModel):
    platform: str
    status: Literal["success", "failed"]
    posted_url: Optional[str] = None
    public_access: bool = False
    date: Optional[str] = None
    time: Optional[str] = None
    error: Optional[str] = None


class PostingResponse(BaseModel):
    success: bool
    results: list[PlatformResult]
