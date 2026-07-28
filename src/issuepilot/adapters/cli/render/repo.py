"""Renderers for repository DTOs.

The JSON shape is a stable machine contract: ``format_version`` changes only
when a field is removed or repurposed. Terminal and Markdown output are
projections of the same DTO, never separately-computed views.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from issuepilot.adapters.cli.console import Console
from issuepilot.repository.application.dto import ManifestDTO, SnapshotDTO

FORMAT_VERSION = 1


def snapshot_json(snapshot: SnapshotDTO) -> dict[str, Any]:
    return {
        "format_version": FORMAT_VERSION,
        "snapshot_id": snapshot.snapshot_id,
        "commit_sha": snapshot.commit_sha,
        "requested_ref": snapshot.requested_ref,
        "locator_fingerprint": snapshot.locator_fingerprint,
        "root_path": snapshot.root_path,
    }


def manifest_json(manifest: ManifestDTO) -> dict[str, Any]:
    return {
        "format_version": FORMAT_VERSION,
        "commit_sha": manifest.commit_sha,
        "requested_ref": manifest.requested_ref,
        "included_count": manifest.included_count,
        "excluded_count": manifest.excluded_count,
        "total_bytes": manifest.total_bytes,
        "languages": dict(manifest.languages),
        "exclusions": dict(manifest.exclusions),
        "sample_paths": list(manifest.sample_paths),
    }


def snapshot_terminal(snapshot: SnapshotDTO, console: Console) -> str:
    return "\n".join(
        [
            f"{console.style('snapshot', 'bold')} {snapshot.snapshot_id}",
            f"  commit  {snapshot.commit_sha}",
            f"  ref     {snapshot.requested_ref}",
            f"  path    {snapshot.root_path}",
        ]
    )


def manifest_terminal(snapshot: SnapshotDTO, manifest: ManifestDTO, console: Console) -> str:
    lines = [
        snapshot_terminal(snapshot, console),
        "",
        f"{console.style('files', 'bold')}",
        f"  analyzable  {manifest.included_count} ({_human_bytes(manifest.total_bytes)})",
        f"  skipped     {manifest.excluded_count}",
    ]
    if manifest.languages:
        lines.extend(["", f"{console.style('languages', 'bold')}"])
        lines.extend(f"  {name:<16} {count}" for name, count in manifest.languages.items())
    if manifest.exclusions:
        lines.extend(["", f"{console.style('skipped because', 'bold')}"])
        lines.extend(f"  {reason:<16} {count}" for reason, count in manifest.exclusions.items())
    return "\n".join(lines)


def manifest_markdown(snapshot: SnapshotDTO, manifest: ManifestDTO) -> str:
    lines = [
        "# Repository map",
        "",
        f"- Commit: `{snapshot.commit_sha}`",
        f"- Requested ref: `{snapshot.requested_ref}`",
        f"- Analyzable files: {manifest.included_count} ({_human_bytes(manifest.total_bytes)})",
        f"- Skipped files: {manifest.excluded_count}",
    ]
    if manifest.languages:
        lines.extend(["", "## Languages", "", "| Language | Files |", "|---|---:|"])
        lines.extend(f"| {name} | {count} |" for name, count in manifest.languages.items())
    if manifest.exclusions:
        lines.extend(["", "## Skipped", "", "| Reason | Files |", "|---|---:|"])
        lines.extend(f"| {reason} | {count} |" for reason, count in manifest.exclusions.items())
    return "\n".join(lines)


def snapshot_list_terminal(snapshots: Sequence[SnapshotDTO], console: Console) -> str:
    if not snapshots:
        return "no snapshots yet — run 'issuepilot repo fetch <url>'"
    header = console.style(f"{'COMMIT':<14} {'REF':<20} SNAPSHOT", "bold")
    rows = [
        f"{s.commit_sha[:12]:<14} {s.requested_ref[:20]:<20} {s.snapshot_id}" for s in snapshots
    ]
    return "\n".join([header, *rows])


def _human_bytes(count: int) -> str:
    size = float(count)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if size < 1024 or unit == "GiB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GiB"
