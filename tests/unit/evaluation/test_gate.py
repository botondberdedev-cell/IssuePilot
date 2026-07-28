from __future__ import annotations

import pytest

from issuepilot.evaluation.domain.gate import (
    DEFAULT_GATE,
    GateOutcome,
    QualityGate,
    Threshold,
)

GATE = QualityGate(
    name="test",
    thresholds=(
        Threshold(metric="citation-validity", minimum=1.0),
        Threshold(metric="pass-rate", minimum=0.5),
        Threshold(metric="claim-grounding", minimum=0.9, mandatory=False),
    ),
)


def test_all_thresholds_met_passes() -> None:
    verdict = GATE.evaluate({"citation-validity": 1.0, "pass-rate": 0.8, "claim-grounding": 0.95})
    assert verdict.passed
    assert verdict.failures == ()


def test_a_mandatory_shortfall_fails() -> None:
    verdict = GATE.evaluate({"citation-validity": 0.99, "pass-rate": 0.8, "claim-grounding": 0.95})
    assert verdict.outcome is GateOutcome.FAILED
    assert [f.metric for f in verdict.failures] == ["citation-validity"]


def test_an_advisory_shortfall_does_not_fail_the_gate() -> None:
    verdict = GATE.evaluate({"citation-validity": 1.0, "pass-rate": 0.8, "claim-grounding": 0.1})
    assert verdict.passed
    assert [f.metric for f in verdict.failures] == ["claim-grounding"]


def test_a_missing_metric_fails_rather_than_passing_silently() -> None:
    """A suite that never produced the number does not get the benefit of the
    doubt."""
    verdict = GATE.evaluate({"pass-rate": 0.8})
    assert not verdict.passed
    assert any(f.metric == "citation-validity" and f.actual is None for f in verdict.failures)


def test_no_metrics_at_all_fails() -> None:
    assert not GATE.evaluate({}).passed


def test_exactly_at_the_threshold_passes() -> None:
    verdict = GATE.evaluate({"citation-validity": 1.0, "pass-rate": 0.5, "claim-grounding": 0.9})
    assert verdict.passed


def test_summary_reports_every_threshold() -> None:
    summary = GATE.evaluate({"citation-validity": 1.0, "pass-rate": 0.2}).summary()
    assert "citation-validity" in summary
    assert "pass-rate" in summary
    assert "MISSING" in summary  # claim-grounding was not produced


def test_a_gate_with_no_thresholds_is_rejected() -> None:
    with pytest.raises(ValueError, match="would pass anything"):
        QualityGate(name="empty", thresholds=())


def test_threshold_must_be_a_fraction() -> None:
    with pytest.raises(ValueError, match=r"within \[0, 1\]"):
        Threshold(metric="x", minimum=1.5)


class TestDefaultGate:
    def test_safety_metrics_demand_perfection(self) -> None:
        absolute = {t.metric for t in DEFAULT_GATE.thresholds if t.minimum == 1.0 and t.mandatory}
        assert {"citation-validity", "forbidden-claim-absence", "honesty"} <= absolute

    def test_a_single_bad_citation_fails_the_default_gate(self) -> None:
        verdict = DEFAULT_GATE.evaluate(
            {
                "citation-validity": 0.99,
                "forbidden-claim-absence": 1.0,
                "honesty": 1.0,
                "required-path-recall": 1.0,
                "pass-rate": 1.0,
                "claim-grounding": 1.0,
            }
        )
        assert not verdict.passed
