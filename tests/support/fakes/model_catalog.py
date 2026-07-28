from __future__ import annotations

from collections.abc import Sequence


class FakeModelCatalog:
    def __init__(self, models: Sequence[str] = ("qwen3", "embeddinggemma")) -> None:
        self._models = tuple(models)

    def list_models(self) -> Sequence[str]:
        return self._models
