"""Structured JSON-lines logging with defensive redaction.

Log output never contains credentials, tokens, private keys, or authenticated
URLs. Redaction is applied to every record as a last line of defense — the
first line is that callers never log secrets in the first place.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import UTC, datetime
from typing import Final, TextIO

REDACTED: Final = "[REDACTED]"

# Order matters: multi-line blocks first, then URLs, then token shapes,
# then generic key=value pairs.
_PATTERNS: Final[list[tuple[re.Pattern[str], str]]] = [
    (
        re.compile(
            r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
            re.DOTALL,
        ),
        "[REDACTED PRIVATE KEY]",
    ),
    # userinfo in URLs: https://user:token@host → https://[REDACTED]@host
    (re.compile(r"(?<=://)[^/@\s]+:[^/@\s]+(?=@)"), REDACTED),
    # GitHub tokens (classic and fine-grained), AWS access key ids
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{16,}\b"), REDACTED),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"), REDACTED),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), REDACTED),
    # authorization headers carry multi-word values ("Bearer <token>")
    (re.compile(r"(?i)\b(authorization)(\s*[=:]\s*)[^\r\n]+"), rf"\1\2{REDACTED}"),
    (re.compile(r"(?i)\bbearer\s+\S+"), REDACTED),
    # generic secret-shaped key/value pairs
    (
        re.compile(r"(?i)\b(password|passwd|secret|token|api[_-]?key)\b(\s*[=:]\s*)\S+"),
        rf"\1\2{REDACTED}",
    ),
]


def redact(text: str) -> str:
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


class RedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(record.getMessage())
        record.args = None
        return True


class JsonLinesFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0] is not None:
            entry["exc_type"] = record.exc_info[0].__name__
        return json.dumps(entry, ensure_ascii=False)


def configure_logging(
    *,
    level: int = logging.INFO,
    stream: TextIO | None = None,
    json_lines: bool = True,
) -> None:
    """Configure the root logger: stderr, redacted, JSON lines by default."""
    handler = logging.StreamHandler(stream if stream is not None else sys.stderr)
    handler.addFilter(RedactionFilter())
    if json_lines:
        handler.setFormatter(JsonLinesFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
