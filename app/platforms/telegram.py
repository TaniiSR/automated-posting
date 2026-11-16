import httpx

from app.config import env
from app.platforms.base import MissingCredentials, Platform, PlatformError, Posted, check

API = "https://api.telegram.org"


class Telegram(Platform):
    """Telegram Bot API: sendMessage to a public channel the bot administers."""

    name = "Telegram"

    async def post(self, client: httpx.AsyncClient, message: str, url: str) -> Posted:
        token, chat_id = env("TELEGRAM_BOT_TOKEN"), env("TELEGRAM_CHAT_ID")
        if not token or not chat_id:
            raise MissingCredentials("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")

        response = check(
            await client.post(
                f"{API}/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": message},
            )
        )
        body = response.json()
        if not body.get("ok"):
            raise PlatformError(f"sendMessage failed: {body.get('description', 'unknown error')}")

        result = body["result"]
        message_id = result.get("message_id")
        if message_id is None:
            raise PlatformError("Telegram response contained no message_id")

        username = self._public_username(result, chat_id)
        if not username:
            raise PlatformError("Telegram chat is not a public channel, so it has no public link")
        return Posted(url=f"https://t.me/{username}/{message_id}")

    @staticmethod
    def _public_username(result: dict, chat_id: str) -> str:
        username = result.get("chat", {}).get("username")
        if username:
            return username
        return chat_id[1:] if chat_id.startswith("@") else ""
