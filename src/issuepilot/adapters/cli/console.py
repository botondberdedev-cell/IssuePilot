"""Terminal output contract.

Standard output carries the deliverable (report, JSON document) and nothing
else. Standard error carries progress, warnings, and diagnostics. Color is
disabled when the stream is not a TTY or ``NO_COLOR`` is set.
"""

from __future__ import annotations

import os
import sys
from enum import StrEnum
from typing import Final, TextIO


class OutputFormat(StrEnum):
    TERMINAL = "terminal"
    MARKDOWN = "markdown"
    JSON = "json"


_ANSI_RESET: Final = "\x1b[0m"
_ANSI: Final = {
    "red": "\x1b[31m",
    "green": "\x1b[32m",
    "yellow": "\x1b[33m",
    "bold": "\x1b[1m",
    "dim": "\x1b[2m",
}


class Console:
    def __init__(
        self,
        *,
        quiet: bool = False,
        color: bool | None = None,
        stdout: TextIO | None = None,
        stderr: TextIO | None = None,
    ) -> None:
        self._stdout = stdout if stdout is not None else sys.stdout
        self._stderr = stderr if stderr is not None else sys.stderr
        self._quiet = quiet
        self._color = self._detect_color() if color is None else color

    def _detect_color(self) -> bool:
        if os.environ.get("NO_COLOR"):
            return False
        return self._stderr.isatty()

    def style(self, text: str, style: str) -> str:
        if not self._color:
            return text
        return f"{_ANSI[style]}{text}{_ANSI_RESET}"

    def out(self, text: str) -> None:
        """Write a line of deliverable output to stdout."""
        print(text, file=self._stdout)

    def progress(self, text: str) -> None:
        if not self._quiet:
            print(text, file=self._stderr)

    def warn(self, text: str) -> None:
        print(self.style(f"warning: {text}", "yellow"), file=self._stderr)

    def error(self, text: str, *, remediation: str | None = None) -> None:
        print(self.style(f"error: {text}", "red"), file=self._stderr)
        if remediation:
            print(self.style(f"  hint: {remediation}", "dim"), file=self._stderr)
