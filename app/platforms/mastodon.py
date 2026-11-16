import httpx

from app.config import env
from app.platforms.base import MissingCredentials, Platform, PlatformError, Posted, check

DEFAULT_INSTANCE = "https://mastodon.social"


class Mastodon(Platform):
    """Mastodon: POST /api/v1/statuses with an access token (write:statuses)."""

    name = "Mastodon"

    async def post(self, client: httpx.AsyncClient, message: str, url: str) -> Posted:
        token = env("MASTODON_ACCESS_TOKEN")
        if not token:
            raise MissingCredentials("MASTODON_ACCESS_TOKEN")
        instance = env("MASTODON_INSTANCE", DEFAULT_INSTANCE).rstrip("/")

        response = check(
            await client.post(
                f"{instance}/api/v1/statuses",
                headers={"Authorization": f"Bearer {token}"},
                data={"status": message, "visibility": "public"},
            )
        )
        post_url = response.json().get("url")
        if not post_url:
            raise PlatformError("Mastodon response contained no post URL")
        return Posted(url=post_url)
