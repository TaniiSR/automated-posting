import os

from dotenv import load_dotenv

load_dotenv()

DEFAULT_TIMEOUT = 20.0


def env(name: str, default: str = "") -> str:
    """Read a setting at call time so environment changes are honoured."""
    return os.getenv(name, default).strip()


def request_timeout() -> float:
    try:
        return float(env("REQUEST_TIMEOUT", str(DEFAULT_TIMEOUT)))
    except ValueError:
        return DEFAULT_TIMEOUT
