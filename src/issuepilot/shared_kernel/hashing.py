"""Canonical hashing helpers.

Everything reproducibility depends on — chunk identity, index keys, prompt
versions, configuration lineage — hashes through these functions so the
canonical form is defined in exactly one place.
"""

from __future__ import annotations

import hashlib
import json

type Json = bool | int | float | str | list["Json"] | dict[str, "Json"] | None


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def content_hash(text: str) -> str:
    """Hash of a text's UTF-8 bytes."""
    return sha256_hex(text.encode("utf-8"))


def canonical_json_hash(obj: Json) -> str:
    """Hash of a JSON-serializable structure, independent of key order."""
    canonical = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return content_hash(canonical)
