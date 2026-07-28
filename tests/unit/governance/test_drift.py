from __future__ import annotations

from issuepilot.governance.domain.drift import DriftVerdict, Window, classify

STABLE = tuple(0.50 + (i % 3) * 0.01 for i in range(20))
SHIFTED = tuple(0.90 + (i % 3) * 0.01 for i in range(20))


def test_similar_windows_are_stable() -> None:
    report = classify(Window("baseline", STABLE), Window("current", STABLE))
    assert report.verdict is DriftVerdict.STABLE
    assert not report.drifted


def test_a_large_shift_is_data_drift() -> None:
    report = classify(Window("baseline", STABLE), Window("current", SHIFTED))
    assert report.verdict is DriftVerdict.DATA_DRIFT
    assert report.drifted


def test_a_small_window_reports_insufficient_data_not_stability() -> None:
    """Absence of evidence must not read as a clean bill of health."""
    report = classify(Window("baseline", (0.5, 0.5)), Window("current", (0.9, 0.9)))
    assert report.verdict is DriftVerdict.INSUFFICIENT_DATA
    assert not report.drifted


def test_concept_drift_requires_labels_on_both_sides() -> None:
    report = classify(
        Window("baseline", STABLE, accuracy=0.9),
        Window("current", STABLE),  # no labels
    )
    assert report.verdict is not DriftVerdict.CONCEPT_DRIFT_SUSPECTED


def test_an_accuracy_drop_with_labels_suspects_concept_drift() -> None:
    report = classify(
        Window("baseline", STABLE, accuracy=0.90),
        Window("current", STABLE, accuracy=0.70),
    )
    assert report.verdict is DriftVerdict.CONCEPT_DRIFT_SUSPECTED
    assert "accuracy fell" in report.detail


def test_concept_drift_outranks_data_drift_when_both_apply() -> None:
    report = classify(
        Window("baseline", STABLE, accuracy=0.95),
        Window("current", SHIFTED, accuracy=0.60),
    )
    assert report.verdict is DriftVerdict.CONCEPT_DRIFT_SUSPECTED


def test_unlabelled_data_drift_says_concept_drift_cannot_be_ruled_out() -> None:
    report = classify(Window("baseline", STABLE), Window("current", SHIFTED))
    assert "cannot be ruled in or out" in report.detail


def test_identical_constant_windows_do_not_divide_by_zero() -> None:
    flat = (0.5,) * 10
    report = classify(Window("baseline", flat), Window("current", flat))
    assert report.effect_size == 0.0
    assert report.verdict is DriftVerdict.STABLE


def test_means_are_reported_for_context() -> None:
    report = classify(Window("baseline", STABLE), Window("current", SHIFTED))
    assert report.baseline_mean < report.current_mean
