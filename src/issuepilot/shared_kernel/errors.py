"""Error taxonomy.

Every failure the tool can report maps to exactly one ``ErrorCategory``, and
every category maps to exactly one process exit code (the CLI contract from
the master plan). Raising an ``IssuePilotError`` subclass anywhere in the
system is sufficient for the CLI to exit correctly.
"""

from __future__ import annotations

from enum import Enum, unique
from types import MappingProxyType
from typing import ClassVar, Final


@unique
class ErrorCategory(Enum):
    USAGE = "usage"
    ACQUISITION = "acquisition"
    MODEL_UNAVAILABLE = "model-unavailable"
    EVIDENCE_UNMET = "evidence-unmet"
    POLICY_DENIED = "policy-denied"
    GATE_FAILED = "gate-failed"
    INTERRUPTED = "interrupted"
    INTERNAL = "internal"


EXIT_CODES: Final = MappingProxyType(
    {
        ErrorCategory.USAGE: 2,
        ErrorCategory.ACQUISITION: 3,
        ErrorCategory.MODEL_UNAVAILABLE: 4,
        ErrorCategory.EVIDENCE_UNMET: 5,
        ErrorCategory.POLICY_DENIED: 6,
        ErrorCategory.GATE_FAILED: 7,
        ErrorCategory.INTERRUPTED: 8,
        ErrorCategory.INTERNAL: 10,
    }
)

EXIT_SUCCESS: Final = 0


class IssuePilotError(Exception):
    """Base for all typed errors; carries a category and a remediation hint."""

    category: ClassVar[ErrorCategory] = ErrorCategory.INTERNAL

    def __init__(self, message: str, *, remediation: str | None = None) -> None:
        super().__init__(message)
        self.remediation = remediation


class UsageError(IssuePilotError):
    """Invalid CLI usage or configuration."""

    category = ErrorCategory.USAGE


class AcquisitionError(IssuePilotError):
    """Repository authentication or acquisition failed."""

    category = ErrorCategory.ACQUISITION


class ModelUnavailableError(IssuePilotError):
    """Ollama or a required model is unavailable."""

    category = ErrorCategory.MODEL_UNAVAILABLE


class EvidenceRequirementError(IssuePilotError):
    """Investigation finished but did not meet evidence requirements."""

    category = ErrorCategory.EVIDENCE_UNMET


class PolicyDeniedError(IssuePilotError):
    """Operation denied by safety policy."""

    category = ErrorCategory.POLICY_DENIED


class QualityGateError(IssuePilotError):
    """Evaluation quality gate failed."""

    category = ErrorCategory.GATE_FAILED


class OperationInterruptedError(IssuePilotError):
    """Run timed out or was cancelled."""

    category = ErrorCategory.INTERRUPTED


class InternalError(IssuePilotError):
    """Unexpected internal failure."""

    category = ErrorCategory.INTERNAL


def exit_code_for(exc: BaseException) -> int:
    """Map any exception to the CLI exit code contract."""
    if isinstance(exc, IssuePilotError):
        return EXIT_CODES[exc.category]
    if isinstance(exc, KeyboardInterrupt):
        return EXIT_CODES[ErrorCategory.INTERRUPTED]
    return EXIT_CODES[ErrorCategory.INTERNAL]
