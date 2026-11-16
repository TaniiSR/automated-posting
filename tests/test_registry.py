from app.main import get_service
from app.platforms.base import Platform
from app.platforms.registry import all_platforms
from app.services.posting_service import PostingService

EXPECTED_NAMES = ["Telegraph", "Mastodon", "Bluesky", "Dev.to", "GitHub Gist", "Telegram"]


def test_registry_contains_all_six_platforms_in_order():
    assert [p.name for p in all_platforms()] == EXPECTED_NAMES


def test_registry_items_are_platforms_with_unique_names():
    platforms = all_platforms()
    assert all(isinstance(p, Platform) for p in platforms)
    assert len({p.name for p in platforms}) == len(platforms)


def test_registry_returns_a_fresh_list_each_call():
    first = all_platforms()
    first.clear()
    assert len(all_platforms()) == 6


def test_default_service_uses_every_registered_platform():
    service = get_service()
    assert isinstance(service, PostingService)
    assert [p.name for p in service.platforms] == EXPECTED_NAMES
