import json

import httpx

from app.config import env
from app.platforms.base import Platform, PlatformError, Posted, check

API = "https://api.telegra.ph"
TITLE_LENGTH = 40


class Telegraph(Platform):
    """Telegraph (telegra.ph): anonymous publishing, no sign-up needed.

    Uses TELEGRAPH_TOKEN if set, otherwise creates an anonymous account."""

    name = "Telegraph"

    async def post(self, client: httpx.AsyncClient, message: str, url: str) -> Posted:
        token = env("TELEGRAPH_TOKEN") or await self._create_account(client)
        page = await self._call(
            client,
            "createPage",
            {
                "access_token": token,
                "title": message[:TITLE_LENGTH],
                "content": json.dumps(self._content(message, url)),
            },
        )
        return Posted(url=page["url"])

    async def _create_account(self, client: httpx.AsyncClient) -> str:
        account = await self._call(client, "createAccount", {"short_name": "poster"})
        return account["access_token"]

    @staticmethod
    async def _call(client: httpx.AsyncClient, method: str, data: dict) -> dict:
        response = check(await client.post(f"{API}/{method}", data=data))
        body = response.json()
        if not body.get("ok"):
            raise PlatformError(f"{method} failed: {body.get('error', 'unknown error')}")
        return body["result"]

    @staticmethod
    def _content(message: str, url: str) -> list[dict]:
        before, _, after = message.partition(url)
        link = {"tag": "a", "attrs": {"href": url}, "children": [url]}
        children = [part for part in (before, link, after) if part]
        return [{"tag": "p", "children": children}]
