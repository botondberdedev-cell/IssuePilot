"""Vector search over a memory-mapped float32 matrix.

Storage per snapshot is an append-only raw float32 file plus a parallel id
file, so adding a batch costs O(batch) rather than rewriting everything
indexed so far. Search memory-maps the matrix, keeping a large index off the
heap and letting the OS page cache do the work.

Because stored and query vectors are both unit-length, the dot product *is*
the cosine similarity — no division, no separate normalization at query time.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Sequence
from pathlib import Path

import numpy as np

_VECTORS_FILE = "vectors.f32"
_IDS_FILE = "ids.txt"
_META_FILE = "meta.json"


class NumpyVectorIndex:
    def __init__(self, root: Path) -> None:
        self._root = root

    def add(self, commit_sha: str, entries: Sequence[tuple[str, tuple[float, ...]]]) -> None:
        if not entries:
            return
        directory = self._directory(commit_sha)
        directory.mkdir(parents=True, exist_ok=True)

        dimension = len(entries[0][1])
        if any(len(vector) != dimension for _, vector in entries):
            raise ValueError("all vectors in a batch must share one dimension")

        existing = self._meta(commit_sha)
        if existing is not None and existing["dimension"] != dimension:
            raise ValueError(
                f"index for {commit_sha[:12]} holds {existing['dimension']}-dimensional "
                f"vectors; refusing to mix in {dimension}-dimensional ones"
            )

        matrix = np.asarray([vector for _, vector in entries], dtype=np.float32)
        with (directory / _VECTORS_FILE).open("ab") as handle:
            handle.write(matrix.tobytes(order="C"))
        with (directory / _IDS_FILE).open("a", encoding="utf-8") as handle:
            handle.writelines(f"{chunk_id}\n" for chunk_id, _ in entries)

        count = (existing["count"] if existing else 0) + len(entries)
        (directory / _META_FILE).write_text(
            json.dumps({"dimension": dimension, "count": count}), encoding="utf-8"
        )

    def search(self, commit_sha: str, query: tuple[float, ...], *, limit: int) -> Sequence[str]:
        meta = self._meta(commit_sha)
        if meta is None or meta["count"] == 0 or limit < 1:
            return []
        dimension = int(meta["dimension"])
        if len(query) != dimension:
            # A query embedded by a different model is not comparable to this
            # index; nothing beats a confidently wrong ranking.
            return []

        directory = self._directory(commit_sha)
        matrix = np.memmap(directory / _VECTORS_FILE, dtype=np.float32, mode="r").reshape(
            -1, dimension
        )
        ids = (directory / _IDS_FILE).read_text(encoding="utf-8").splitlines()
        usable = min(len(ids), matrix.shape[0])
        if usable == 0:
            return []

        scores = np.asarray(matrix[:usable] @ np.asarray(query, dtype=np.float32))
        top = min(limit, usable)
        # argpartition finds the top-k without sorting everything; only those
        # k are then ordered.
        candidates = np.argpartition(-scores, top - 1)[:top]
        ordered = candidates[np.argsort(-scores[candidates], kind="stable")]
        return [ids[int(i)] for i in ordered]

    def clear(self, commit_sha: str) -> None:
        shutil.rmtree(self._directory(commit_sha), ignore_errors=True)

    def _directory(self, commit_sha: str) -> Path:
        return self._root / commit_sha

    def _meta(self, commit_sha: str) -> dict[str, int] | None:
        path = self._directory(commit_sha) / _META_FILE
        if not path.is_file():
            return None
        loaded: dict[str, int] = json.loads(path.read_text(encoding="utf-8"))
        return loaded
