from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from issuepilot.shared_kernel.hashing import Json, canonical_json_hash, content_hash
from issuepilot.shared_kernel.ids import is_ulid, new_ulid, ulid_timestamp_ms
from issuepilot.shared_kernel.result import Err, Ok, unwrap, unwrap_err

timestamps = st.integers(min_value=0, max_value=(1 << 48) - 1)

json_values: st.SearchStrategy[Json] = st.recursive(
    st.none() | st.booleans() | st.integers() | st.text(),
    lambda children: (
        st.lists(children, max_size=4) | st.dictionaries(st.text(max_size=8), children, max_size=4)
    ),
    max_leaves=10,
)


@given(timestamps)
def test_ulid_timestamp_roundtrips(ts: int) -> None:
    ulid = new_ulid(ts)
    assert is_ulid(ulid)
    assert ulid_timestamp_ms(ulid) == ts


@given(timestamps, timestamps)
def test_ulid_ordering_follows_timestamps(a: int, b: int) -> None:
    if a < b:
        assert new_ulid(a) < new_ulid(b)
    elif b < a:
        assert new_ulid(b) < new_ulid(a)


@given(st.text())
def test_content_hash_is_deterministic(text: str) -> None:
    assert content_hash(text) == content_hash(text)
    assert len(content_hash(text)) == 64


@given(json_values)
def test_canonical_json_hash_is_deterministic(value: Json) -> None:
    assert canonical_json_hash(value) == canonical_json_hash(value)


@given(st.integers())
def test_result_unwrap_laws(x: int) -> None:
    assert unwrap(Ok(x)) == x
    assert unwrap_err(Err(x)) == x
