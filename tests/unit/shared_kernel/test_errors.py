from __future__ import annotations

import pytest

from issuepilot.shared_kernel.errors import (
    EXIT_CODES,
    EXIT_SUCCESS,
    AcquisitionError,
    ErrorCategory,
    EvidenceRequirementError,
    InternalError,
    IssuePilotError,
    ModelUnavailableError,
    OperationInterruptedError,
    PolicyDeniedError,
    QualityGateError,
    UsageError,
    exit_code_for,
)

EXPECTED_CONTRACT: dict[ErrorCategory, int] = {
    ErrorCategory.USAGE: 2,
    ErrorCategory.ACQUISITION: 3,
    ErrorCategory.MODEL_UNAVAILABLE: 4,
    ErrorCategory.EVIDENCE_UNMET: 5,
    ErrorCategory.POLICY_DENIED: 6,
    ErrorCategory.GATE_FAILED: 7,
    ErrorCategory.INTERRUPTED: 8,
    ErrorCategory.INTERNAL: 10,
}


def test_exit_code_table_matches_cli_contract() -> None:
    assert dict(EXIT_CODES) == EXPECTED_CONTRACT
    assert EXIT_SUCCESS == 0


def test_every_category_has_an_exit_code() -> None:
    assert set(EXIT_CODES) == set(ErrorCategory)


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (UsageError("bad flag"), 2),
        (AcquisitionError("auth failed"), 3),
        (ModelUnavailableError("ollama down"), 4),
        (EvidenceRequirementError("no evidence"), 5),
        (PolicyDeniedError("denied"), 6),
        (QualityGateError("gate failed"), 7),
        (OperationInterruptedError("cancelled"), 8),
        (InternalError("boom"), 10),
    ],
)
def test_exit_code_for_each_error_type(error: IssuePilotError, code: int) -> None:
    assert exit_code_for(error) == code


def test_keyboard_interrupt_maps_to_interrupted() -> None:
    assert exit_code_for(KeyboardInterrupt()) == 8


def test_unknown_exception_maps_to_internal() -> None:
    assert exit_code_for(ValueError("surprise")) == 10


def test_remediation_hint_is_carried() -> None:
    error = AcquisitionError("host key unknown", remediation="add the host to known_hosts")
    assert error.remediation == "add the host to known_hosts"
    assert str(error) == "host key unknown"
