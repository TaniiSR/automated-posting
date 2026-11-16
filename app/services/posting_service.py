import asyncio
from datetime import datetime
from typing import Callable, Optional

import httpx

from app.config import request_timeout
from app.platforms.base import Platform, PlatformError
from app.schemas import PlatformResult, PostingResponse


def describe_error(exc: Exception) -> str:
    if isinstance(exc, PlatformError):
        return str(exc)
    detail = str(exc)
    name = type(exc).__name__
    return f"{name}: {detail}" if detail else name


class PostingService:
    def __init__(
        self,
        platforms: list[Platform],
        client: Optional[httpx.AsyncClient] = None,
        now: Callable[[], datetime] = datetime.now,
    ):
        self.platforms = platforms
        self.client = client
        self.now = now

    async def publish(self, message: str, url: str) -> PostingResponse:
        if self.client is not None:
            results = await self._run_all(self.client, message, url)
        else:
            async with httpx.AsyncClient(timeout=request_timeout()) as client:
                results = await self._run_all(client, message, url)
        return PostingResponse(
            success=any(r.status == "success" for r in results),
            results=results,
        )

    async def _run_all(
        self, client: httpx.AsyncClient, message: str, url: str
    ) -> list[PlatformResult]:
        tasks = [self._run_one(platform, client, message, url) for platform in self.platforms]
        return list(await asyncio.gather(*tasks))

    async def _run_one(
        self, platform: Platform, client: httpx.AsyncClient, message: str, url: str
    ) -> PlatformResult:
        try:
            posted = await platform.post(client, message, url)
        except Exception as exc:
            return PlatformResult(
                platform=platform.name, status="failed", error=describe_error(exc)
            )
        moment = self.now()
        return PlatformResult(
            platform=platform.name,
            status="success",
            posted_url=posted.url,
            public_access=await self._is_public(client, posted.url),
            date=moment.date().isoformat(),
            time=moment.strftime("%H:%M:%S"),
        )

    @staticmethod
    async def _is_public(client: httpx.AsyncClient, url: str) -> bool:
        try:
            response = await client.get(url, follow_redirects=True)
        except httpx.HTTPError:
            return False
        return response.status_code == 200
