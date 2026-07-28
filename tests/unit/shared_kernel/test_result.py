from __future__ import annotations

import dataclasses

import pytest

from issuepilot.shared_kernel.result import Err, Ok, Result, UnwrapError, unwrap, unwrap_err


def test_pattern_matching_distinguishes_variants() -> None:
    result: Result[int, str] = Ok(42)
    match result:
        case Ok(value):
            assert value == 42
        case Err():
            pytest.fail("expected Ok")


def test_unwrap_ok_returns_value() -> None:
    assert unwrap(Ok(7)) == 7


def test_unwrap_err_returns_error() -> None:
    assert unwrap_err(Err("boom")) == "boom"


def test_unwrap_wrong_variant_raises_with_payload() -> None:
    with pytest.raises(UnwrapError) as exc_info:
        unwrap(Err("boom"))
    assert exc_info.value.payload == "boom"

    with pytest.raises(UnwrapError) as exc_info:
        unwrap_err(Ok(7))
    assert exc_info.value.payload == 7


def test_variants_are_immutable() -> None:
    ok = Ok(1)
    with pytest.raises(dataclasses.FrozenInstanceError):
        ok.value = 2  # type: ignore[misc]
