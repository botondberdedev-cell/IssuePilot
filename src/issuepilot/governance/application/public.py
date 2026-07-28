"""The governance context's public facade."""

from __future__ import annotations

from issuepilot.governance.domain.routing import RoutingTable
from issuepilot.governance.domain.values import ModelReference, TaskClass


class GovernanceFacade:
    def __init__(self, routing: RoutingTable) -> None:
        self._routing = routing

    def route(self, task: TaskClass) -> ModelReference:
        return self._routing.route(task)
