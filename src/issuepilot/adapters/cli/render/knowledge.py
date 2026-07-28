"""Renderers for knowledge DTOs."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from issuepilot.adapters.cli.console import Console
from issuepilot.knowledge.application.dto import IndexStatsDTO, SearchHitDTO

FORMAT_VERSION = 1
_SNIPPET_LINES = 6


def stats_json(stats: IndexStatsDTO) -> dict[str, Any]:
    return {
        "format_version": FORMAT_VERSION,
        "commit_sha": stats.commit_sha,
        "chunk_count": stats.chunk_count,
        "indexed_files": stats.indexed_files,
        "has_semantic": stats.has_semantic,
    }


def hits_json(hits: Sequence[SearchHitDTO]) -> dict[str, Any]:
    return {
        "format_version": FORMAT_VERSION,
        "results": [
            {
                "path": hit.path,
                "start_line": hit.start_line,
                "end_line": hit.end_line,
                "commit_sha": hit.commit_sha,
                "symbol": hit.symbol,
                "score": round(hit.score, 6),
                "sources": list(hit.sources),
                "snippet": hit.snippet,
            }
            for hit in hits
        ],
    }


def stats_terminal(stats: IndexStatsDTO, console: Console) -> str:
    retrieval = "lexical + semantic" if stats.has_semantic else "lexical only"
    return "\n".join(
        [
            f"{console.style('indexed', 'bold')} {stats.commit_sha[:12]}",
            f"  files    {stats.indexed_files}",
            f"  chunks   {stats.chunk_count}",
            f"  search   {retrieval}",
        ]
    )


def hits_terminal(hits: Sequence[SearchHitDTO], console: Console) -> str:
    if not hits:
        return "no matches"
    blocks: list[str] = []
    for hit in hits:
        location = console.style(f"{hit.path}:{hit.start_line}-{hit.end_line}", "bold")
        symbol = f" ({hit.symbol})" if hit.symbol else ""
        found_by = console.style(f"[{'+'.join(hit.sources)}]", "dim")
        snippet = "\n".join(f"    {line}" for line in hit.snippet.splitlines()[:_SNIPPET_LINES])
        blocks.append(f"{location}{symbol} {found_by}\n{snippet}")
    return "\n\n".join(blocks)


def hits_markdown(hits: Sequence[SearchHitDTO]) -> str:
    if not hits:
        return "_no matches_"
    lines = ["# Search results", ""]
    for hit in hits:
        lines.extend(
            [
                f"## `{hit.path}:{hit.start_line}-{hit.end_line}`",
                "",
                f"Found by: {', '.join(hit.sources)} @ `{hit.commit_sha[:12]}`",
                "",
                "```",
                hit.snippet.rstrip(),
                "```",
                "",
            ]
        )
    return "\n".join(lines)
