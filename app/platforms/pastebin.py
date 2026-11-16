import httpx

from app.config import env
from app.platforms.base import MissingCredentials, Platform, PlatformError, Posted, check
from app.platforms.text import make_title

API = "https://pastebin.com/api/api_post.php"
PASTE_URL_PREFIX = "https://pastebin.com/"


class Pastebin(Platform):
    """Pastebin: create a public paste with an API dev key.

    Pastebin replies with plain text and reports errors as text with HTTP 200,
    so anything that is not a paste URL is treated as a failure."""

    name = "Pastebin"

    async def post(self, client: httpx.AsyncClient, message: str, url: str) -> Posted:
        api_key = env("PASTEBIN_API_KEY")
        if not api_key:
            raise MissingCredentials("PASTEBIN_API_KEY")

        response = check(
            await client.post(
                API,
                data={
                    "api_dev_key": api_key,
                    "api_option": "paste",
                    "api_paste_code": message,
                    "api_paste_name": make_title(message, url),
                    "api_paste_private": "0",  # 0 = public
                    "api_paste_expire_date": "N",  # never expires
                },
            )
        )
        text = response.text.strip()
        if not text.startswith(PASTE_URL_PREFIX):
            raise PlatformError(f"Pastebin error: {text[:150] or 'empty response'}")
        return Posted(url=text)
