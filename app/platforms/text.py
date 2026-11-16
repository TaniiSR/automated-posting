def make_title(message: str, url: str, limit: int = 80, fallback: str = "New update") -> str:
    """A short title: the message without its link, trimmed to `limit` characters."""
    title = message.replace(url, "").strip(" -:|").strip()
    return title[:limit] or fallback
