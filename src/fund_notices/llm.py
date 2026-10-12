"""The one small interface the rest of the code uses to talk to an LLM.

Everything else depends on LLMClient only. OllamaClient is the real model on this
laptop. CachedClient wraps any client and saves each reply on disk, so a rerun
costs nothing and gives the same answer. Tests use a fake client instead.
See docs/DECISIONS.md, entries 6 and 7.
"""

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Protocol

import ollama

MODEL_ENV_VAR = "FUND_NOTICES_MODEL"


class LLMClient(Protocol):
    """Anything that can answer a prompt with JSON that fits a schema."""

    @property
    def name(self) -> str:
        """The model name. It is part of the cache key."""
        ...

    def complete_json(self, system: str, prompt: str, schema: dict[str, Any]) -> str:
        """Return the model's reply as a JSON string."""
        ...


def model_from_env() -> str:
    """The model name set in the environment, for example qwen3:4b."""
    name = os.environ.get(MODEL_ENV_VAR)
    if not name:
        raise RuntimeError(f"Set {MODEL_ENV_VAR} to an Ollama model name, for example qwen3:4b")
    return name


class OllamaClient:
    """Calls a model served by Ollama on this laptop."""

    def __init__(self, model: str) -> None:
        self._model = model
        self._client = ollama.Client()

    @property
    def name(self) -> str:
        return self._model

    def complete_json(self, system: str, prompt: str, schema: dict[str, Any]) -> str:
        response = self._client.chat(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            # Ollama only lets the model write JSON that fits this schema.
            format=schema,
            # Temperature 0 makes the model pick its most likely answer every time.
            options={"temperature": 0},
        )
        return response.message.content or ""


class CachedClient:
    """Wraps a client and keeps every reply in a folder, keyed by a hash of the request."""

    def __init__(self, inner: LLMClient, folder: Path) -> None:
        self.inner = inner
        self.folder = folder
        self.model_calls = 0
        self.cache_hits = 0

    @property
    def name(self) -> str:
        return self.inner.name

    def complete_json(self, system: str, prompt: str, schema: dict[str, Any]) -> str:
        request = json.dumps([self.name, system, prompt, schema], sort_keys=True)
        path = self.folder / f"{hashlib.sha256(request.encode()).hexdigest()}.json"
        if path.is_file():
            self.cache_hits += 1
            return path.read_text(encoding="utf-8")
        reply = self.inner.complete_json(system, prompt, schema)
        self.model_calls += 1
        self.folder.mkdir(parents=True, exist_ok=True)
        path.write_text(reply, encoding="utf-8")
        return reply
