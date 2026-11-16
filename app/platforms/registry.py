from app.platforms.base import Platform
from app.platforms.bluesky import Bluesky
from app.platforms.devto import DevTo
from app.platforms.gist import GithubGist
from app.platforms.mastodon import Mastodon
from app.platforms.pastebin import Pastebin
from app.platforms.telegraph import Telegraph


def all_platforms() -> list[Platform]:
    return [Telegraph(), Mastodon(), Bluesky(), DevTo(), GithubGist(), Pastebin()]
