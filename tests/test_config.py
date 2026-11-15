from app import config


def test_env_returns_value_set_in_environment(monkeypatch):
    monkeypatch.setenv("SOME_TOKEN", "abc123")
    assert config.env("SOME_TOKEN") == "abc123"


def test_env_reads_at_call_time(monkeypatch):
    monkeypatch.setenv("SOME_TOKEN", "first")
    assert config.env("SOME_TOKEN") == "first"
    monkeypatch.setenv("SOME_TOKEN", "second")
    assert config.env("SOME_TOKEN") == "second"


def test_env_missing_returns_empty_string(monkeypatch):
    monkeypatch.delenv("SOME_TOKEN", raising=False)
    assert config.env("SOME_TOKEN") == ""


def test_env_missing_returns_given_default(monkeypatch):
    monkeypatch.delenv("SOME_TOKEN", raising=False)
    assert config.env("SOME_TOKEN", "fallback") == "fallback"


def test_env_strips_whitespace(monkeypatch):
    monkeypatch.setenv("SOME_TOKEN", "  abc \n")
    assert config.env("SOME_TOKEN") == "abc"


def test_request_timeout_defaults_to_20(monkeypatch):
    monkeypatch.delenv("REQUEST_TIMEOUT", raising=False)
    assert config.request_timeout() == 20.0


def test_request_timeout_reads_env(monkeypatch):
    monkeypatch.setenv("REQUEST_TIMEOUT", "5.5")
    assert config.request_timeout() == 5.5


def test_request_timeout_invalid_value_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("REQUEST_TIMEOUT", "not-a-number")
    assert config.request_timeout() == 20.0
