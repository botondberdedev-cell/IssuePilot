"""Ports required by governance use cases (skeleton set; grows in v0.2)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol


class ModelCatalogPort(Protocol):
    """The locally available models (served by the Ollama adapter)."""

    def list_models(self) -> Sequence[str]: ...
