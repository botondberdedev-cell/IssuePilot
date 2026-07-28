"""Architecture boundaries fail plain ``pytest``, not just CI.

Runs import-linter programmatically against pyproject.toml so a broken
contract shows up in the default test run.
"""

from __future__ import annotations

import subprocess  # noqa: TID251 - test invokes the project's own tooling
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_all_import_contracts_hold() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "importlinter.cli", "lint_imports"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert completed.returncode == 0, (
        f"import-linter reported broken contracts:\n{completed.stdout}\n{completed.stderr}"
    )
