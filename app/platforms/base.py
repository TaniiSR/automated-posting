from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx


class PlatformError(Exception):
    """Any expected platform failure: bad credentials, API error, bad response."""


class MissingCredentials(PlatformError):
    def __init__(self, *names: str):
        super().__init__(f"Missing credentials: set {', '.join(names)}")


@dataclass
class Posted:
    url: str


def check(response: httpx.Response, ok: tuple[int, ...] = (200, 201)) -> httpx.Response:
    if response.status_code not in ok:
        body = response.text[:200].replace("\n", " ")
        raise PlatformError(f"HTTP {response.status_code}: {body}")
    return response


class Platform(ABC):
    name: str

    @abstractmethod
    async def post(self, client: httpx.AsyncClient, message: str, url: str) -> Posted:
        """Publish the message and return the public URL of the new post."""
