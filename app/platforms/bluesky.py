from datetime import datetime, timezone

import httpx

from app.config import env
from app.platforms.base import MissingCredentials, Platform, PlatformError, Posted, check

XRPC = "https://bsky.social/xrpc"
COLLECTION = "app.bsky.feed.post"


class Bluesky(Platform):
    """Bluesky (AT Protocol): log in with an app password, then create a post record."""

    name = "Bluesky"

    async def post(self, client: httpx.AsyncClient, message: str, url: str) -> Posted:
        handle, password = env("BLUESKY_HANDLE"), env("BLUESKY_APP_PASSWORD")
        if not handle or not password:
            raise MissingCredentials("BLUESKY_HANDLE", "BLUESKY_APP_PASSWORD")

        token, did = await self._login(client, handle, password)
        created = check(
            await client.post(
                f"{XRPC}/com.atproto.repo.createRecord",
                headers={"Authorization": f"Bearer {token}"},
                json={"repo": did, "collection": COLLECTION, "record": self._record(message, url)},
            )
        ).json()

        uri = created.get("uri")
        if not uri:
            raise PlatformError("Bluesky response contained no uri")
        rkey = uri.rsplit("/", 1)[-1]
        return Posted(url=f"https://bsky.app/profile/{did}/post/{rkey}")

    @staticmethod
    async def _login(client: httpx.AsyncClient, handle: str, password: str) -> tuple[str, str]:
        session = check(
            await client.post(
                f"{XRPC}/com.atproto.server.createSession",
                json={"identifier": handle, "password": password},
            )
        ).json()
        token, did = session.get("accessJwt"), session.get("did")
        if not token or not did:
            raise PlatformError("Bluesky session response was incomplete")
        return token, did

    @staticmethod
    def _record(message: str, url: str) -> dict:
        record = {
            "$type": COLLECTION,
            "text": message,
            "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        position = message.find(url)
        if position >= 0:
            # Bluesky measures link positions in UTF-8 bytes, not characters.
            start = len(message[:position].encode("utf-8"))
            end = start + len(url.encode("utf-8"))
            record["facets"] = [
                {
                    "index": {"byteStart": start, "byteEnd": end},
                    "features": [{"$type": "app.bsky.richtext.facet#link", "uri": url}],
                }
            ]
        return record
