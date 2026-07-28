"""Contract suite for RepositoryAcquirerPort.

The real adapter is exercised against a local fixture repository under the
``integration`` marker; the fake covers the same behavioural contract in the
fast suite.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from issuepilot.repository.application.ports import RepositoryAcquirerPort
from issuepilot.repository.domain.snapshot import AcquisitionOptions
from issuepilot.repository.domain.values import RepositoryLocator, RepositoryRef
from issuepilot.repository.infrastructure.git_acquirer import GitRepositoryAcquirer
from issuepilot.repository.infrastructure.workspace import WorkspaceLayout
from issuepilot.shared_kernel.errors import AcquisitionError
from tests.support.fakes.repository import FakeRepositoryAcquirer
from tests.support.fixture_repos import build_simple_repo

OPTIONS = AcquisitionOptions(history_depth=5)


@pytest.fixture(
    params=[
        pytest.param("fake", id="fake"),
        pytest.param("real", id="real", marks=pytest.mark.integration),
    ]
)
def acquirer_and_locator(
    request: pytest.FixtureRequest, tmp_path: Path
) -> Iterator[tuple[RepositoryAcquirerPort, RepositoryLocator, str]]:
    if request.param == "fake":
        fake = FakeRepositoryAcquirer()
        fake.seed("main", commit_sha="a" * 40)
        yield fake, RepositoryLocator.parse("https://example.com/x/y.git"), "a" * 40
        return

    repo = build_simple_repo(tmp_path / "source")
    layout = WorkspaceLayout(tmp_path / "workspace")
    locator = RepositoryLocator.parse(repo.locator, allow_local_path=True)
    yield GitRepositoryAcquirer(layout), locator, repo.head_sha


def test_acquire_pins_the_expected_commit(
    acquirer_and_locator: tuple[RepositoryAcquirerPort, RepositoryLocator, str],
) -> None:
    acquirer, locator, expected_sha = acquirer_and_locator
    result = acquirer.acquire(locator, RepositoryRef("main"), OPTIONS)
    assert result.commit_sha.value == expected_sha


def test_acquire_returns_a_root_path(
    acquirer_and_locator: tuple[RepositoryAcquirerPort, RepositoryLocator, str],
) -> None:
    acquirer, locator, _ = acquirer_and_locator
    assert acquirer.acquire(locator, RepositoryRef("main"), OPTIONS).root_path


def test_repeated_acquisition_is_stable(
    acquirer_and_locator: tuple[RepositoryAcquirerPort, RepositoryLocator, str],
) -> None:
    acquirer, locator, _ = acquirer_and_locator
    first = acquirer.acquire(locator, RepositoryRef("main"), OPTIONS)
    second = acquirer.acquire(locator, RepositoryRef("main"), OPTIONS)
    assert first.commit_sha == second.commit_sha
    assert first.root_path == second.root_path


def test_unknown_ref_raises_acquisition_error(
    acquirer_and_locator: tuple[RepositoryAcquirerPort, RepositoryLocator, str],
) -> None:
    acquirer, locator, _ = acquirer_and_locator
    with pytest.raises(AcquisitionError):
        acquirer.acquire(locator, RepositoryRef("no-such-ref"), OPTIONS)


def test_default_ref_is_reported(
    acquirer_and_locator: tuple[RepositoryAcquirerPort, RepositoryLocator, str],
) -> None:
    acquirer, locator, _ = acquirer_and_locator
    assert acquirer.default_ref(locator).value == "main"
