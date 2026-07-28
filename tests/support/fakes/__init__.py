"""Fake adapters and the port → fake registry.

``FAKES_BY_PORT`` is the explicit map from every application-layer port
Protocol to its fake implementation. The arch conventions test walks each
context's ``application/ports.py`` and fails when a port is missing here or
lacks a contract suite — adding a port deliberately costs a fake and a
contract module.
"""

from __future__ import annotations

from tests.support.fakes.citations import FakeCitationVerifier
from tests.support.fakes.embeddings import FakeEmbedder
from tests.support.fakes.eventbus import RecordingEventBus
from tests.support.fakes.feedback_store import InMemoryFeedbackStore
from tests.support.fakes.model_catalog import FakeModelCatalog
from tests.support.fakes.reasoning import FakeReasoningModel
from tests.support.fakes.repository import (
    FakeRepositoryAcquirer,
    FakeSnapshotReader,
    InMemorySnapshotStore,
)
from tests.support.fakes.run_store import InMemoryRunStore
from tests.support.fakes.search import FakeSearch
from tests.support.fakes.tracker import FakeExperimentTracker

FAKES_BY_PORT: dict[str, type] = {
    # repository
    "SnapshotStorePort": InMemorySnapshotStore,
    "RepositoryAcquirerPort": FakeRepositoryAcquirer,
    "SnapshotReaderPort": FakeSnapshotReader,
    # knowledge
    "EmbeddingGeneratorPort": FakeEmbedder,
    # investigation
    "ReasoningModelPort": FakeReasoningModel,
    "SearchPort": FakeSearch,
    "CitationVerifierPort": FakeCitationVerifier,
    "RunStorePort": InMemoryRunStore,
    # evaluation
    "ExperimentTrackerPort": FakeExperimentTracker,
    # governance
    "ModelCatalogPort": FakeModelCatalog,
    # feedback
    "FeedbackStorePort": InMemoryFeedbackStore,
    # shared kernel
    "EventBus": RecordingEventBus,
}
