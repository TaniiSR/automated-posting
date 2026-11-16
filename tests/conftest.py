import pytest

APP_SETTINGS = [
    "REQUEST_TIMEOUT",
    "TELEGRAPH_TOKEN",
    "MASTODON_INSTANCE",
    "MASTODON_ACCESS_TOKEN",
    "BLUESKY_HANDLE",
    "BLUESKY_APP_PASSWORD",
    "DEVTO_API_KEY",
    "GITHUB_TOKEN",
    "PASTEBIN_API_KEY",
]


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch):
    """Tests must never depend on a developer's real .env file."""
    for name in APP_SETTINGS:
        monkeypatch.delenv(name, raising=False)
