"""Identifier types and generation.

All aggregate identifiers are ULIDs: 26-character Crockford base32 strings that
are lexicographically sortable by creation time. Each aggregate gets its own
``NewType`` so identifiers cannot be mixed up at type-check time.
"""

from __future__ import annotations

import os
import time
from typing import Final, NewType, Protocol

SnapshotId = NewType("SnapshotId", str)
IndexId = NewType("IndexId", str)
RunId = NewType("RunId", str)
ReportId = NewType("ReportId", str)
EvalCaseId = NewType("EvalCaseId", str)
EvalRunId = NewType("EvalRunId", str)
FeedbackId = NewType("FeedbackId", str)
EventId = NewType("EventId", str)

_CROCKFORD: Final = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_CROCKFORD_SET: Final = frozenset(_CROCKFORD)
ULID_LENGTH: Final = 26
_TIMESTAMP_CHARS: Final = 10
_RANDOM_CHARS: Final = 16
_MAX_TIMESTAMP_MS: Final = (1 << 48) - 1


class IdGenerator(Protocol):
    """Source of fresh identifiers; injected so tests can be deterministic."""

    def new_id(self) -> str: ...


class UlidGenerator:
    """Default generator: real time, real randomness."""

    def new_id(self) -> str:
        return new_ulid()


def new_ulid(timestamp_ms: int | None = None) -> str:
    """Generate a ULID; ``timestamp_ms`` overrides the time part for determinism."""
    ts = time.time_ns() // 1_000_000 if timestamp_ms is None else timestamp_ms
    if not 0 <= ts <= _MAX_TIMESTAMP_MS:
        raise ValueError(f"ULID timestamp out of range: {ts}")
    randomness = int.from_bytes(os.urandom(10))
    return _encode(ts, _TIMESTAMP_CHARS) + _encode(randomness, _RANDOM_CHARS)


def is_ulid(value: str) -> bool:
    return len(value) == ULID_LENGTH and all(c in _CROCKFORD_SET for c in value)


def ulid_timestamp_ms(value: str) -> int:
    """Extract the millisecond timestamp encoded in a ULID."""
    if not is_ulid(value):
        raise ValueError(f"not a ULID: {value!r}")
    result = 0
    for char in value[:_TIMESTAMP_CHARS]:
        result = (result << 5) | _CROCKFORD.index(char)
    return result


def _encode(value: int, length: int) -> str:
    chars: list[str] = []
    for _ in range(length):
        chars.append(_CROCKFORD[value & 0x1F])
        value >>= 5
    return "".join(reversed(chars))
