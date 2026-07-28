"""Cooperative cancellation.

A ``CancellationToken`` is set by the CLI's SIGINT handler (or a timeout
watchdog) and polled by long-running loops — acquisition, indexing, agent
steps. Cancellation is always graceful: loops observe the token at safe
checkpoints and persist resumable state before exiting.
"""

from __future__ import annotations

import threading

from issuepilot.shared_kernel.errors import OperationInterruptedError


class CancellationToken:
    """Thread-safe, one-way cancellation flag."""

    __slots__ = ("_event",)

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        if self._event.is_set():
            raise OperationInterruptedError(
                "operation cancelled",
                remediation="the run state is persisted; use 'issuepilot run resume' to continue",
            )


NEVER_CANCELLED = CancellationToken()
"""Shared token for call sites that do not participate in cancellation."""
