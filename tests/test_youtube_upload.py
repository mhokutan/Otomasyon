import importlib

import youtube_upload


def test_configured_scopes_defaults_when_env_missing(monkeypatch):
    monkeypatch.delenv("YT_SCOPES", raising=False)
    module = importlib.reload(youtube_upload)
    assert module._configured_scopes() == module.SCOPES


def test_configured_scopes_parses_commas_and_whitespace(monkeypatch):
    monkeypatch.setenv(
        "YT_SCOPES",
        "scope.one scope.two,scope.three\n https://example.com/custom",
    )
    # Reload to ensure module level caches don't interfere with env lookups.
    module = importlib.reload(youtube_upload)
    assert module._configured_scopes() == [
        "scope.one",
        "scope.two",
        "scope.three",
        "https://example.com/custom",
    ]

