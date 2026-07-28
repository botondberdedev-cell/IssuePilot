from __future__ import annotations

from datetime import UTC, datetime

import pytest

from issuepilot.governance.domain.registry import (
    ConfigurationRecord,
    Role,
    decide_promotion,
)
from issuepilot.governance.domain.values import ModelReference, TaskClass

NOW = datetime(2026, 7, 28, tzinfo=UTC)
DATASET = "dataset-hash-1"

CLEAN = {
    "citation-validity": 1.0,
    "forbidden-claim-absence": 1.0,
    "honesty": 1.0,
    "pass-rate": 0.8,
}


def record(role: Role, metrics: dict[str, float], *, dataset: str = DATASET) -> ConfigurationRecord:
    return ConfigurationRecord(
        configuration_id=f"{role.value}-1",
        task=TaskClass.CHAT,
        model=ModelReference("qwen3:8b"),
        role=role,
        dataset_hash=dataset,
        metrics=metrics,
        promoted_at=NOW if role is Role.CHAMPION else None,
    )


class TestPromotion:
    def test_the_first_configuration_is_promoted(self) -> None:
        decision = decide_promotion(None, record(Role.CHALLENGER, CLEAN))
        assert decision.promoted

    def test_an_improvement_is_promoted(self) -> None:
        champion = record(Role.CHAMPION, CLEAN)
        challenger = record(Role.CHALLENGER, CLEAN | {"pass-rate": 0.9})
        assert decide_promotion(champion, challenger).promoted

    def test_an_equal_result_is_promoted(self) -> None:
        assert decide_promotion(
            record(Role.CHAMPION, CLEAN), record(Role.CHALLENGER, CLEAN)
        ).promoted

    def test_a_pass_rate_drop_is_refused(self) -> None:
        champion = record(Role.CHAMPION, CLEAN)
        challenger = record(Role.CHALLENGER, CLEAN | {"pass-rate": 0.5})
        decision = decide_promotion(champion, challenger)
        assert not decision.promoted
        assert "pass-rate fell" in decision.explain()

    def test_a_small_drop_within_tolerance_is_allowed(self) -> None:
        champion = record(Role.CHAMPION, CLEAN)
        challenger = record(Role.CHALLENGER, CLEAN | {"pass-rate": 0.78})
        assert decide_promotion(champion, challenger, tolerance=0.05).promoted


class TestSafetyRegressions:
    @pytest.mark.parametrize("metric", ["citation-validity", "forbidden-claim-absence", "honesty"])
    def test_any_safety_regression_blocks_promotion(self, metric: str) -> None:
        champion = record(Role.CHAMPION, CLEAN)
        challenger = record(Role.CHALLENGER, CLEAN | {metric: 0.99, "pass-rate": 0.99})
        decision = decide_promotion(champion, challenger)
        assert not decision.promoted
        assert metric in decision.explain()

    def test_tolerance_does_not_apply_to_safety_metrics(self) -> None:
        """A big win elsewhere cannot buy back a bad citation."""
        champion = record(Role.CHAMPION, CLEAN)
        challenger = record(Role.CHALLENGER, CLEAN | {"citation-validity": 0.9, "pass-rate": 1.0})
        assert not decide_promotion(champion, challenger, tolerance=0.5).promoted


class TestComparability:
    def test_different_datasets_cannot_be_compared(self) -> None:
        champion = record(Role.CHAMPION, CLEAN)
        challenger = record(Role.CHALLENGER, CLEAN, dataset="other-hash")
        decision = decide_promotion(champion, challenger)
        assert not decision.promoted
        assert "different datasets" in decision.explain()


class TestRecordInvariants:
    def test_a_champion_must_name_its_dataset(self) -> None:
        with pytest.raises(ValueError, match="dataset"):
            ConfigurationRecord(
                configuration_id="c",
                task=TaskClass.CHAT,
                model=ModelReference("qwen3:8b"),
                role=Role.CHAMPION,
                dataset_hash="",
                promoted_at=NOW,
            )

    def test_a_champion_must_record_when_it_was_promoted(self) -> None:
        with pytest.raises(ValueError, match="promoted"):
            ConfigurationRecord(
                configuration_id="c",
                task=TaskClass.CHAT,
                model=ModelReference("qwen3:8b"),
                role=Role.CHAMPION,
                dataset_hash=DATASET,
            )

    def test_a_challenger_needs_no_promotion_evidence(self) -> None:
        assert record(Role.CHALLENGER, CLEAN).promoted_at is None
