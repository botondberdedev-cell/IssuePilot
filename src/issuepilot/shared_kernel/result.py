"""A minimal Result type for explicit, typed error handling.

Usage favors structural pattern matching::

    match acquire(locator):
        case Ok(snapshot):
            ...
        case Err(error):
            ...
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import final


class UnwrapError(Exception):
    """Raised when unwrapping the wrong variant; carries the payload."""

    def __init__(self, payload: object) -> None:
        super().__init__(f"unexpected Result variant; payload: {payload!r}")
        self.payload = payload


@final
@dataclass(frozen=True, slots=True)
class Ok[T]:
    value: T


@final
@dataclass(frozen=True, slots=True)
class Err[E]:
    error: E


type Result[T, E] = Ok[T] | Err[E]


def unwrap[T, E](result: Result[T, E]) -> T:
    """Return the ``Ok`` value or raise ``UnwrapError``. Test/edge convenience."""
    match result:
        case Ok(value):
            return value
        case Err(error):
            raise UnwrapError(error)


def unwrap_err[T, E](result: Result[T, E]) -> E:
    """Return the ``Err`` payload or raise ``UnwrapError``. Test/edge convenience."""
    match result:
        case Ok(value):
            raise UnwrapError(value)
        case Err(error):
            return error
