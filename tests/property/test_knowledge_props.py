from __future__ import annotations

import string

from hypothesis import given
from hypothesis import strategies as st

from issuepilot.knowledge.domain.chunking import chunk_document
from issuepilot.knowledge.domain.fusion import reciprocal_rank_fusion

SHA = "a" * 40

file_text = st.text(alphabet=string.ascii_letters + string.digits + " \n\t_.()=:#", max_size=600)
keys = st.text(alphabet=string.ascii_lowercase, min_size=1, max_size=5)
key_lists = st.lists(keys, max_size=8, unique=True)


@given(file_text)
def test_chunking_is_deterministic(text: str) -> None:
    first = chunk_document(commit_sha=SHA, path="f.txt", text=text, language=None)
    second = chunk_document(commit_sha=SHA, path="f.txt", text=text, language=None)
    assert [c.chunk_id for c in first] == [c.chunk_id for c in second]


@given(file_text)
def test_chunks_have_valid_ranges_within_the_file(text: str) -> None:
    total_lines = len(text.splitlines())
    for produced in chunk_document(commit_sha=SHA, path="f.txt", text=text, language=None):
        assert 1 <= produced.start_line <= produced.end_line <= max(total_lines, 1)


@given(file_text)
def test_chunk_text_always_matches_its_recorded_span(text: str) -> None:
    lines = text.splitlines(keepends=True)
    for produced in chunk_document(commit_sha=SHA, path="f.txt", text=text, language=None):
        assert produced.text == "".join(lines[produced.start_line - 1 : produced.end_line])


@given(file_text)
def test_no_chunk_is_whitespace_only(text: str) -> None:
    chunks = chunk_document(commit_sha=SHA, path="f.txt", text=text, language=None)
    assert all(c.text.strip() for c in chunks)


@given(file_text)
def test_python_chunking_never_raises(text: str) -> None:
    chunk_document(commit_sha=SHA, path="f.py", text=text, language="Python")


@given(key_lists, key_lists)
def test_fusion_output_is_the_union_of_inputs(lexical: list[str], semantic: list[str]) -> None:
    fused = reciprocal_rank_fusion({"lexical": lexical, "semantic": semantic})
    assert {r.key for r in fused} == set(lexical) | set(semantic)


@given(key_lists, key_lists)
def test_fusion_scores_are_sorted_descending(lexical: list[str], semantic: list[str]) -> None:
    fused = reciprocal_rank_fusion({"lexical": lexical, "semantic": semantic})
    scores = [r.score for r in fused]
    assert scores == sorted(scores, reverse=True)


@given(key_lists, key_lists)
def test_fusion_is_order_independent_across_sources(
    lexical: list[str], semantic: list[str]
) -> None:
    forward = reciprocal_rank_fusion({"lexical": lexical, "semantic": semantic})
    backward = reciprocal_rank_fusion({"semantic": semantic, "lexical": lexical})
    assert [r.key for r in forward] == [r.key for r in backward]
