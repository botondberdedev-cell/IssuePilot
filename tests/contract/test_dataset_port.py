"""Contract suite for DatasetPort: fake and the JSONL repository."""

from __future__ import annotations

from pathlib import Path

import pytest

from issuepilot.evaluation.application.ports import DatasetPort
from issuepilot.evaluation.infrastructure.dataset_repo import JsonlDatasetRepository
from issuepilot.shared_kernel.errors import UsageError
from tests.support.fakes.evaluation import InMemoryDatasetRepository, sample_case

LINE = (
    '{"case_id": "case-1", "issue": "Where is the retry handled?", '
    '"category": "bug-location", "fixture": "self", "expected_paths": ["webhook.py"]}'
)


@pytest.fixture(params=["fake", "jsonl"])
def datasets(request: pytest.FixtureRequest, tmp_path: Path) -> DatasetPort:
    if request.param == "fake":
        return InMemoryDatasetRepository([sample_case()])
    (tmp_path / "fake.jsonl").write_text(LINE + "\n", encoding="utf-8")
    return JsonlDatasetRepository(tmp_path)


def test_loading_yields_cases(datasets: DatasetPort) -> None:
    dataset = datasets.load("fake")
    assert len(dataset) == 1
    assert dataset.cases[0].case_id == "case-1"


def test_a_dataset_reports_a_version(datasets: DatasetPort) -> None:
    assert datasets.load("fake").version


def test_available_lists_at_least_the_loadable_one(datasets: DatasetPort) -> None:
    assert "fake" in datasets.available()


def test_categories_are_countable(datasets: DatasetPort) -> None:
    assert datasets.load("fake").category_counts() == {"bug-location": 1}


class TestJsonlSpecifics:
    def test_an_unknown_dataset_is_a_usage_error(self, tmp_path: Path) -> None:
        with pytest.raises(UsageError, match="no evaluation dataset"):
            JsonlDatasetRepository(tmp_path).load("absent")

    def test_a_malformed_line_names_its_line_number(self, tmp_path: Path) -> None:
        (tmp_path / "broken.jsonl").write_text(
            LINE + '\n{"case_id": "x", "issue": "y"}\n', encoding="utf-8"
        )
        with pytest.raises(UsageError, match="line 2"):
            JsonlDatasetRepository(tmp_path).load("broken")

    def test_blank_lines_are_ignored(self, tmp_path: Path) -> None:
        (tmp_path / "spaced.jsonl").write_text(
            f"{LINE}\n\n{LINE.replace('case-1', 'case-2')}\n", encoding="utf-8"
        )
        assert len(JsonlDatasetRepository(tmp_path).load("spaced")) == 2

    def test_the_shipped_core_dataset_loads(self) -> None:
        """The dataset in the repository must always be valid."""
        dataset = JsonlDatasetRepository(Path("eval_data")).load("core")
        assert len(dataset) >= 5
        assert dataset.category_counts()
