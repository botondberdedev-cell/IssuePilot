from __future__ import annotations

import pytest

from issuepilot.evaluation.domain.case import CaseCategory, EvaluationCase
from issuepilot.evaluation.domain.scoring import ScoredReport, aggregate, score_case
from issuepilot.shared_kernel.ids import EvalCaseId

SHA = "4f2a7c1b9e83" + "0" * 28


def case(**overrides: object) -> EvaluationCase:
    defaults: dict[str, object] = {
        "case_id": EvalCaseId("case-1"),
        "issue": "Refunds stay pending.",
        "category": CaseCategory.BUG_LOCATION,
        "fixture": "simple",
        "expected_paths": ("refunds/webhook.py",),
    }
    return EvaluationCase(**(defaults | overrides))  # type: ignore[arg-type]


def report(**overrides: object) -> ScoredReport:
    defaults: dict[str, object] = {
        "commit_sha": SHA,
        "completeness": "complete",
        "claims": ("The retry path drops the transition.",),
        "citations": (f"src/refunds/webhook.py:84-121 @ {SHA[:12]}",),
        "speculative_claims": (),
        "missing_information": (),
    }
    return ScoredReport(**(defaults | overrides))  # type: ignore[arg-type]


class TestCitationValidity:
    def test_a_well_formed_citation_of_this_snapshot_is_valid(self) -> None:
        assert score_case(case(), report()).citation_validity == 1.0

    def test_a_citation_of_another_snapshot_is_invalid(self) -> None:
        scored = score_case(
            case(), report(citations=("src/refunds/webhook.py:84-121 @ deadbeef1234",))
        )
        assert scored.citation_validity == 0.0

    def test_an_unparseable_citation_is_invalid(self) -> None:
        scored = score_case(case(), report(citations=("somewhere in the webhook file",)))
        assert scored.citation_validity == 0.0

    def test_an_inverted_line_range_is_invalid(self) -> None:
        scored = score_case(
            case(), report(citations=(f"src/refunds/webhook.py:200-10 @ {SHA[:12]}",))
        )
        assert scored.citation_validity == 0.0

    def test_validity_is_a_fraction_of_all_citations(self) -> None:
        scored = score_case(
            case(),
            report(
                citations=(
                    f"src/refunds/webhook.py:84-121 @ {SHA[:12]}",
                    "garbage",
                )
            ),
        )
        assert scored.citation_validity == 0.5

    def test_no_citations_is_vacuously_valid(self) -> None:
        """Nothing invalid was said; whether something *should* have been
        cited is required-path-recall's question, not this one."""
        assert score_case(case(), report(citations=())).citation_validity == 1.0


class TestRequiredPathRecall:
    def test_citing_the_expected_file_scores_full(self) -> None:
        assert score_case(case(), report()).required_path_recall == 1.0

    def test_citing_the_wrong_file_scores_zero(self) -> None:
        scored = score_case(case(), report(citations=(f"src/other.py:1-5 @ {SHA[:12]}",)))
        assert scored.required_path_recall == 0.0

    def test_expectations_match_on_a_path_suffix(self) -> None:
        """A case names refunds/webhook.py without pinning the fixture layout."""
        scored = score_case(
            case(expected_paths=("webhook.py",)),
            report(citations=(f"deep/nested/src/webhook.py:1-5 @ {SHA[:12]}",)),
        )
        assert scored.required_path_recall == 1.0

    def test_partial_recall_across_several_expected_paths(self) -> None:
        scored = score_case(
            case(expected_paths=("webhook.py", "state.py")),
            report(citations=(f"src/webhook.py:1-5 @ {SHA[:12]}",)),
        )
        assert scored.required_path_recall == 0.5


class TestClaimGrounding:
    def test_all_grounded_claims_score_full(self) -> None:
        assert score_case(case(), report()).claim_grounding == 1.0

    def test_speculation_lowers_the_score(self) -> None:
        scored = score_case(
            case(),
            report(
                claims=("Grounded claim.", "A guess."),
                speculative_claims=("A guess.",),
            ),
        )
        assert scored.claim_grounding == 0.5


class TestForbiddenClaims:
    def test_a_forbidden_phrase_fails_the_case(self) -> None:
        scored = score_case(
            case(forbidden_claims=("race condition",)),
            report(claims=("This is caused by a RACE CONDITION in the worker.",)),
        )
        assert scored.forbidden_claim_absence == 0.0
        assert not scored.passed

    def test_absence_of_forbidden_phrases_passes(self) -> None:
        scored = score_case(case(forbidden_claims=("race condition",)), report())
        assert scored.forbidden_claim_absence == 1.0


class TestHonesty:
    def test_admitting_ignorance_when_expected_scores_full(self) -> None:
        scored = score_case(
            case(expected_paths=(), expect_incomplete=True),
            report(
                claims=("Possibly unrelated.",),
                speculative_claims=("Possibly unrelated.",),
                missing_information=("The repository does not contain this.",),
                completeness="partial",
            ),
        )
        assert scored.honesty == 1.0

    def test_inventing_an_answer_when_none_exists_fails(self) -> None:
        """The exact failure this product is built to prevent."""
        scored = score_case(
            case(expected_paths=(), expect_incomplete=True),
            report(claims=("The bug is definitely in the retry handler.",)),
        )
        assert scored.honesty == 0.0
        assert not scored.passed

    def test_honesty_does_not_apply_to_ordinary_cases(self) -> None:
        assert score_case(case(), report()).honesty == 1.0


class TestAggregate:
    def test_averages_each_metric_and_reports_a_pass_rate(self) -> None:
        good = score_case(case(), report())
        bad = score_case(case(), report(citations=("garbage",)))
        summary = aggregate([good, bad])
        assert summary["citation-validity"] == 0.5
        assert summary["pass-rate"] == 0.5

    def test_no_scores_yields_no_metrics(self) -> None:
        """An empty suite must not look like a perfect one."""
        assert aggregate([]) == {}


class TestCaseValidation:
    def test_a_case_that_checks_nothing_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="nothing would be checked"):
            case(expected_paths=())

    def test_a_case_cannot_both_expect_paths_and_incompleteness(self) -> None:
        with pytest.raises(ValueError, match="cannot be both"):
            case(expect_incomplete=True)
