import httpx

from app.config import env
from app.platforms.base import MissingCredentials, Platform, PlatformError, Posted, check

API = "https://dev.to/api/articles"
TITLE_LENGTH = 80
FALLBACK_TITLE = "New update"


class DevTo(Platform):
    """Dev.to (Forem API): publish an article with an API key."""

    name = "Dev.to"

    async def post(self, client: httpx.AsyncClient, message: str, url: str) -> Posted:
        api_key = env("DEVTO_API_KEY")
        if not api_key:
            raise MissingCredentials("DEVTO_API_KEY")

        response = check(
            await client.post(
                API,
                headers={"api-key": api_key},
                json={
                    "article": {
                        "title": self._title(message, url),
                        "body_markdown": message,
                        "published": True,
                    }
                },
            )
        )
        article_url = response.json().get("url")
        if not article_url:
            raise PlatformError("Dev.to response contained no article URL")
        return Posted(url=article_url)

    @staticmethod
    def _title(message: str, url: str) -> str:
        title = message.replace(url, "").strip(" -:|").strip()
        return title[:TITLE_LENGTH] or FALLBACK_TITLE
