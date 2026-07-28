from __future__ import annotations

import threading

import pytest

from issuepilot.shared_kernel.cancellation import NEVER_CANCELLED, CancellationToken
from issuepilot.shared_kernel.errors import OperationInterruptedError


def test_fresh_token_is_not_cancelled() -> None:
    token = CancellationToken()
    assert not token.cancelled
    token.raise_if_cancelled()  # must not raise


def test_cancel_sets_flag_and_raises() -> None:
    token = CancellationToken()
    token.cancel()
    assert token.cancelled
    with pytest.raises(OperationInterruptedError) as exc_info:
        token.raise_if_cancelled()
    assert exc_info.value.remediation is not None


def test_cancellation_is_visible_across_threads() -> None:
    token = CancellationToken()
    thread = threading.Thread(target=token.cancel)
    thread.start()
    thread.join()
    assert token.cancelled


def test_never_cancelled_sentinel() -> None:
    assert not NEVER_CANCELLED.cancelled
