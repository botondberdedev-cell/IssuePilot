"""Resource budgets for acquisition.

A repository is untrusted input, and "how big is it" is not knowable before
fetching. The budget is therefore checked *as* the manifest is built: the
first file that pushes the running total past the limit stops the work, so a
pathological repository costs a bounded amount of reading rather than an
unbounded one.
"""

from __future__ import annotations

from dataclasses import dataclass

from issuepilot.shared_kernel.errors import PolicyDeniedError


@dataclass(frozen=True, slots=True)
class SizeBudget:
    """Total analyzable bytes allowed for one snapshot."""

    max_total_bytes: int

    def __post_init__(self) -> None:
        if self.max_total_bytes < 1:
            raise ValueError(f"size budget must be positive, got {self.max_total_bytes}")

    def check(self, accumulated_bytes: int, *, file_count: int) -> None:
        """Raise when the running total has passed the limit."""
        if accumulated_bytes > self.max_total_bytes:
            raise PolicyDeniedError(
                f"repository exceeds the {_human(self.max_total_bytes)} size budget "
                f"({_human(accumulated_bytes)} across {file_count} analyzable files)",
                remediation=(
                    "raise repository.max_total_bytes in issuepilot.toml, "
                    "or investigate a narrower ref"
                ),
            )


def _human(count: int) -> str:
    size = float(count)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if size < 1024 or unit == "GiB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GiB"
