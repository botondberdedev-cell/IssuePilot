"""Contract suite for ModelCatalogPort (Ollama adapter joins in v0.2)."""

from __future__ import annotations

import pytest

from issuepilot.governance.application.ports import ModelCatalogPort
from tests.support.fakes.model_catalog import FakeModelCatalog


@pytest.fixture(params=["fake"])
def catalog(request: pytest.FixtureRequest) -> ModelCatalogPort:
    return FakeModelCatalog(("qwen3", "embeddinggemma"))


def test_lists_model_names(catalog: ModelCatalogPort) -> None:
    models = catalog.list_models()
    assert models
    assert all(m.strip() for m in models)


def test_listing_is_stable(catalog: ModelCatalogPort) -> None:
    assert list(catalog.list_models()) == list(catalog.list_models())
