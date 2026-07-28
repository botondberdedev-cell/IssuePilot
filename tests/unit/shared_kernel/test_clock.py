from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from issuepilot.shared_kernel.clock import FixedClock, SystemClock


def test_system_clock_returns_aware_utc() -> None:
    now = SystemClock().now()
    assert now.tzinfo is UTC


def test_fixed_clock_is_deterministic_and_advanceable() -> None:
    instant = datetime(2026, 7, 28, 12, 0, tzinfo=UTC)
    clock = FixedClock(instant)
    assert clock.now() == instant
    assert clock.now() == instant
    clock.advance(timedelta(minutes=5))
    assert clock.now() == instant + timedelta(minutes=5)


def test_fixed_clock_rejects_naive_datetime() -> None:
    with pytest.raises(ValueError, match="aware"):
        FixedClock(datetime(2026, 7, 28, 12, 0))
