from __future__ import annotations

import pytest

from issuepilot.shared_kernel.ids import (
    ULID_LENGTH,
    UlidGenerator,
    is_ulid,
    new_ulid,
    ulid_timestamp_ms,
)


def test_new_ulid_has_correct_shape() -> None:
    ulid = new_ulid()
    assert len(ulid) == ULID_LENGTH
    assert is_ulid(ulid)


def test_timestamp_roundtrips() -> None:
    ts = 1_722_000_000_123
    assert ulid_timestamp_ms(new_ulid(ts)) == ts


def test_ulids_sort_by_timestamp() -> None:
    earlier = new_ulid(1_000)
    later = new_ulid(2_000)
    assert earlier < later


def test_out_of_range_timestamp_rejected() -> None:
    with pytest.raises(ValueError, match="out of range"):
        new_ulid(-1)
    with pytest.raises(ValueError, match="out of range"):
        new_ulid(1 << 48)


@pytest.mark.parametrize("bad", ["", "short", "!" * 26, "i" * 26, "0" * 25, "0" * 27])
def test_is_ulid_rejects_malformed(bad: str) -> None:
    assert not is_ulid(bad)


def test_ulid_timestamp_ms_rejects_malformed() -> None:
    with pytest.raises(ValueError, match="not a ULID"):
        ulid_timestamp_ms("nope")


def test_generator_produces_unique_valid_ids() -> None:
    generator = UlidGenerator()
    ids = {generator.new_id() for _ in range(100)}
    assert len(ids) == 100
    assert all(is_ulid(i) for i in ids)
