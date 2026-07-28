from __future__ import annotations

import pytest

from issuepilot.repository.domain.limits import SizeBudget
from issuepilot.shared_kernel.errors import PolicyDeniedError


def test_within_budget_passes() -> None:
    SizeBudget(max_total_bytes=1000).check(999, file_count=3)


def test_exactly_at_the_budget_passes() -> None:
    SizeBudget(max_total_bytes=1000).check(1000, file_count=3)


def test_over_budget_is_denied_with_remediation() -> None:
    with pytest.raises(PolicyDeniedError) as exc_info:
        SizeBudget(max_total_bytes=1000).check(1001, file_count=4)
    assert "size budget" in str(exc_info.value)
    assert exc_info.value.remediation is not None


def test_message_reports_human_sizes_and_file_count() -> None:
    with pytest.raises(PolicyDeniedError) as exc_info:
        SizeBudget(max_total_bytes=1_048_576).check(2_097_152, file_count=42)
    message = str(exc_info.value)
    assert "MiB" in message
    assert "42" in message


def test_nonpositive_budget_is_rejected() -> None:
    with pytest.raises(ValueError, match="positive"):
        SizeBudget(max_total_bytes=0)
