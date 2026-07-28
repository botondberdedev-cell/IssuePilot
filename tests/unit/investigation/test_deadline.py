from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from issuepilot.investigation.domain.deadline import Deadline
from issuepilot.shared_kernel.errors import OperationInterruptedError

START = datetime(2026, 7, 28, 12, 0, tzinfo=UTC)


def test_not_expired_before_the_limit() -> None:
    deadline = Deadline.of_seconds(START, 60)
    assert not deadline.expired(START + timedelta(seconds=59))


def test_expired_exactly_at_the_limit() -> None:
    deadline = Deadline.of_seconds(START, 60)
    assert deadline.expired(START + timedelta(seconds=60))


def test_remaining_counts_down_and_floors_at_zero() -> None:
    deadline = Deadline.of_seconds(START, 60)
    assert deadline.remaining(START + timedelta(seconds=20)) == timedelta(seconds=40)
    assert deadline.remaining(START + timedelta(seconds=999)) == timedelta(0)


def test_raise_if_expired_carries_remediation() -> None:
    deadline = Deadline.of_seconds(START, 60)
    deadline.raise_if_expired(START)  # must not raise
    with pytest.raises(OperationInterruptedError) as exc_info:
        deadline.raise_if_expired(START + timedelta(seconds=61))
    assert exc_info.value.remediation is not None


def test_naive_start_is_rejected() -> None:
    with pytest.raises(ValueError, match="aware"):
        Deadline(started_at=datetime(2026, 7, 28, 12, 0), limit=timedelta(seconds=1))


def test_nonpositive_limit_is_rejected() -> None:
    with pytest.raises(ValueError, match="positive"):
        Deadline(started_at=START, limit=timedelta(0))
