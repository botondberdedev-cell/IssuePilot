from __future__ import annotations

import pytest

from issuepilot.governance.domain.routing import RoutingTable
from issuepilot.governance.domain.values import ModelReference, TaskClass

FULL_TABLE = {
    TaskClass.CHAT: ModelReference("qwen3"),
    TaskClass.EMBEDDING: ModelReference("embeddinggemma"),
    TaskClass.SUMMARIZE: ModelReference("qwen3"),
}


def test_routes_every_task_class() -> None:
    table = RoutingTable(FULL_TABLE)
    assert table.route(TaskClass.CHAT).name == "qwen3"
    assert table.route(TaskClass.EMBEDDING).name == "embeddinggemma"


def test_partial_table_is_rejected() -> None:
    partial = {TaskClass.CHAT: ModelReference("qwen3")}
    with pytest.raises(ValueError, match="not total"):
        RoutingTable(partial)


def test_empty_model_name_is_rejected() -> None:
    with pytest.raises(ValueError, match="empty"):
        ModelReference("  ")
