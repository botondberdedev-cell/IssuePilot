"""Fake adapters and the port → fake registry.

``FAKES_BY_PORT`` is the explicit map from every application-layer port
Protocol to its fake. The arch conventions test walks each context's
``application/ports.py`` and fails when a port is missing here or lacks a
contract suite — so adding a port deliberately costs a fake and a contract
module.
"""

from __future__ import annotations

from tests.support.fakes.embeddings import FakeEmbedder
from tests.support.fakes.evaluation import (
    FakeExperimentTracker,
    InMemoryDatasetRepository,
    ScriptedCaseRunner,
)
from tests.support.fakes.eventbus import RecordingEventBus
from tests.support.fakes.feedback_store import InMemoryFeedbackStore
from tests.support.fakes.investigation import (
    FakeCitationVerifier,
    FakeFileReader,
    FakePrompts,
    FakeSearch,
    InMemoryRunStore,
    ScriptedReasoningModel,
)
from tests.support.fakes.knowledge import (
    FakeSource,
    InMemoryChunkStore,
    InMemoryLexicalIndex,
    InMemoryVectorIndex,
)
from tests.support.fakes.model_catalog import FakeModelCatalog
from tests.support.fakes.repository import (
    FakeRepositoryAcquirer,
    FakeSnapshotReader,
    InMemorySnapshotStore,
)

FAKES_BY_PORT: dict[str, type] = {
    # repository
    "SnapshotStorePort": InMemorySnapshotStore,
    "RepositoryAcquirerPort": FakeRepositoryAcquirer,
    "SnapshotReaderPort": FakeSnapshotReader,
    # knowledge
    "EmbeddingGeneratorPort": FakeEmbedder,
    "SourcePort": FakeSource,
    "ChunkStorePort": InMemoryChunkStore,
    "LexicalIndexPort": InMemoryLexicalIndex,
    "VectorIndexPort": InMemoryVectorIndex,
    # investigation
    "ReasoningModelPort": ScriptedReasoningModel,
    "PromptPort": FakePrompts,
    "SearchPort": FakeSearch,
    "FileReaderPort": FakeFileReader,
    "CitationVerifierPort": FakeCitationVerifier,
    "RunStorePort": InMemoryRunStore,
    # evaluation
    "ExperimentTrackerPort": FakeExperimentTracker,
    "DatasetPort": InMemoryDatasetRepository,
    "InvestigationRunnerPort": ScriptedCaseRunner,
    # governance
    "ModelCatalogPort": FakeModelCatalog,
    # feedback
    "FeedbackStorePort": InMemoryFeedbackStore,
    # shared kernel
    "EventBus": RecordingEventBus,
}
