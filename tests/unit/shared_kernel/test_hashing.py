from __future__ import annotations

from issuepilot.shared_kernel.hashing import Json, canonical_json_hash, content_hash, sha256_hex

SHA256_EMPTY = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def test_sha256_known_vector() -> None:
    assert sha256_hex(b"") == SHA256_EMPTY


def test_content_hash_uses_utf8() -> None:
    assert content_hash("héllo") == sha256_hex("héllo".encode())


def test_canonical_json_hash_is_key_order_independent() -> None:
    a: Json = {"x": 1, "y": [1, 2, {"z": None}]}
    b: Json = {"y": [1, 2, {"z": None}], "x": 1}
    assert canonical_json_hash(a) == canonical_json_hash(b)


def test_canonical_json_hash_distinguishes_values() -> None:
    assert canonical_json_hash({"x": 1}) != canonical_json_hash({"x": 2})
