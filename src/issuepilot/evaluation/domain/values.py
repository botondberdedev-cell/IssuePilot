"""Evaluation-context value objects."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

_METRIC_NAME_RE: Final = re.compile(r"^[a-z][a-z0-9-]*$")


@dataclass(frozen=True, slots=True)
class MetricName:
    """Kebab-case metric identifier, e.g. ``required-file-recall``."""

    value: str

    def __post_init__(self) -> None:
        if not _METRIC_NAME_RE.match(self.value):
            raise ValueError(f"metric names are kebab-case identifiers, got {self.value!r}")
