from __future__ import annotations

import pytest

from backend.ai_secret_store import SecretStore


def test_secret_store_round_trip_and_delete(tmp_path) -> None:
    store = SecretStore(tmp_path / "llm-secrets.sqlite3")

    store.set_secret("OPENROUTER_API_KEY", "secret-value")

    assert store.count() == 1
    assert store.has_secret("OPENROUTER_API_KEY") is True
    assert store.get_secret("OPENROUTER_API_KEY") == "secret-value"

    store.delete_secret("OPENROUTER_API_KEY")

    assert store.count() == 0
    assert store.has_secret("OPENROUTER_API_KEY") is False


def test_secret_store_requires_non_empty_values(tmp_path) -> None:
    store = SecretStore(tmp_path / "llm-secrets.sqlite3")

    with pytest.raises(ValueError):
        store.set_secret("", "secret-value")

    with pytest.raises(ValueError):
        store.set_secret("OPENROUTER_API_KEY", "")

    with pytest.raises(KeyError):
        store.get_secret("MISSING")
