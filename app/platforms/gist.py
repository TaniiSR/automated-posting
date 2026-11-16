import httpx

from app.config import env
from app.platforms.base import MissingCredentials, Platform, PlatformError, Posted, check

API = "https://api.github.com/gists"
FILENAME = "post.md"


class GithubGist(Platform):
    """GitHub Gist: create a public gist with a token that has the gist scope."""

    name = "GitHub Gist"

    async def post(self, client: httpx.AsyncClient, message: str, url: str) -> Posted:
        token = env("GITHUB_TOKEN")
        if not token:
            raise MissingCredentials("GITHUB_TOKEN")

        response = check(
            await client.post(
                API,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                    "User-Agent": "automated-posting",
                },
                json={
                    "description": message,
                    "public": True,
                    "files": {FILENAME: {"content": message}},
                },
            )
        )
        gist_url = response.json().get("html_url")
        if not gist_url:
            raise PlatformError("GitHub response contained no gist URL")
        return Posted(url=gist_url)
