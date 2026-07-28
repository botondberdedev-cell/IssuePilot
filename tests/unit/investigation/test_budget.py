from __future__ import annotations

import pytest

from issuepilot.investigation.domain.budget import (
    BudgetExhaustedError,
    DurationBudget,
    StepBudget,
    TokenBudget,
)


class TestStepBudget:
    def test_spending_returns_new_instance(self) -> None:
        budget = StepBudget(limit=3)
        spent = budget.spend()
        assert budget.spent == 0  # original untouched
        assert spent.spent == 1
        assert spent.remaining == 2

    def test_exhaustion_is_reached_exactly_at_limit(self) -> None:
        budget = StepBudget(limit=2).spend().spend()
        assert budget.exhausted

    def test_spending_past_limit_raises(self) -> None:
        budget = StepBudget(limit=1).spend()
        with pytest.raises(BudgetExhaustedError, match="step budget exhausted"):
            budget.spend()

    def test_can_never_be_constructed_negative(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            StepBudget(limit=0)
        with pytest.raises(ValueError, match="outside"):
            StepBudget(limit=5, spent=6)
        with pytest.raises(ValueError, match="outside"):
            StepBudget(limit=5, spent=-1)


class TestTokenBudget:
    def test_spend_accumulates(self) -> None:
        budget = TokenBudget(limit=100).spend(60).spend(40)
        assert budget.exhausted

    def test_overspend_raises(self) -> None:
        with pytest.raises(BudgetExhaustedError, match="token budget exhausted"):
            TokenBudget(limit=100).spend(101)

    def test_negative_spend_rejected(self) -> None:
        with pytest.raises(ValueError, match="negative"):
            TokenBudget(limit=100).spend(-1)


class TestDurationBudget:
    def test_expiry_is_pure(self) -> None:
        budget = DurationBudget(limit_seconds=600)
        assert not budget.expired(599.9)
        assert budget.expired(600.0)

    def test_nonpositive_limit_rejected(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            DurationBudget(limit_seconds=0)
