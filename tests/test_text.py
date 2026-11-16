from app.platforms.text import make_title

URL = "https://example.com"


def test_title_is_the_message_without_the_link():
    assert make_title(f"Grow your visibility {URL}", URL) == "Grow your visibility"


def test_title_strips_separators_left_around_the_link():
    assert make_title(f"Big news: {URL}", URL) == "Big news"
    assert make_title(f"{URL} - big news", URL) == "big news"


def test_title_falls_back_when_nothing_is_left():
    assert make_title(URL, URL) == "New update"


def test_title_is_cut_to_the_limit():
    assert len(make_title("w" * 190 + f" {URL}", URL)) == 80


def test_limit_and_fallback_can_be_changed():
    assert make_title("abcdef " + URL, URL, limit=3) == "abc"
    assert make_title(URL, URL, fallback="Hi") == "Hi"
