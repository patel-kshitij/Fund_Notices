from pathlib import Path
from typing import Any

import pytest

from fund_notices.llm import MODEL_ENV_VAR, CachedClient, model_from_env


class CountingClient:
    """A fake model that answers with how many times it was called."""

    def __init__(self, name: str = "fake") -> None:
        self._name = name
        self.calls = 0

    @property
    def name(self) -> str:
        return self._name

    def complete_json(self, system: str, prompt: str, schema: dict[str, Any]) -> str:
        self.calls += 1
        return f'{{"call": {self.calls}}}'


def test_cache_returns_the_saved_reply_without_calling_the_model(tmp_path: Path) -> None:
    inner = CountingClient()
    first = CachedClient(inner, tmp_path).complete_json("s", "p", {})
    again = CachedClient(inner, tmp_path)
    assert again.complete_json("s", "p", {}) == first
    assert inner.calls == 1
    assert (again.model_calls, again.cache_hits) == (0, 1)


def test_cache_keeps_the_model_time_for_reruns(tmp_path: Path) -> None:
    first = CachedClient(CountingClient(), tmp_path)
    first.complete_json("s", "p", {})
    again = CachedClient(CountingClient(), tmp_path)
    again.complete_json("s", "p", {})
    assert again.model_calls == 0
    assert again.model_seconds == first.model_seconds > 0


def test_cache_key_covers_prompt_schema_and_model(tmp_path: Path) -> None:
    inner = CountingClient()
    client = CachedClient(inner, tmp_path)
    client.complete_json("s", "p", {})
    client.complete_json("s", "other prompt", {})
    client.complete_json("s", "p", {"type": "object"})
    CachedClient(CountingClient("other model"), tmp_path).complete_json("s", "p", {})
    assert inner.calls == 3
    assert len(list(tmp_path.glob("*.json"))) == 4


def test_model_name_must_be_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(MODEL_ENV_VAR, raising=False)
    with pytest.raises(RuntimeError, match=MODEL_ENV_VAR):
        model_from_env()
    monkeypatch.setenv(MODEL_ENV_VAR, "qwen3:4b")
    assert model_from_env() == "qwen3:4b"
