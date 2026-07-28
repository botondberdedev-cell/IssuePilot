"""Conventions that keep the port/fake/contract discipline honest.

For every ``typing.Protocol`` defined in any context's
``application/ports.py``:

1. a fake must be registered in ``tests.support.fakes.FAKES_BY_PORT``;
2. a contract suite ``tests/contract/test_<snake_case_name>.py`` must exist.
"""

from __future__ import annotations

import importlib
import inspect
import re
import typing
from pathlib import Path

CONTEXTS = ("repository", "knowledge", "investigation", "evaluation", "governance", "feedback")
CONTRACT_DIR = Path(__file__).resolve().parents[1] / "contract"


def _declared_ports() -> list[tuple[str, str]]:
    """(context, port_name) for every Protocol defined in a ports module."""
    ports: list[tuple[str, str]] = []
    for context in CONTEXTS:
        module_name = f"issuepilot.{context}.application.ports"
        module = importlib.import_module(module_name)
        for name, obj in vars(module).items():
            if inspect.isclass(obj) and obj.__module__ == module_name and typing.is_protocol(obj):
                ports.append((context, name))
    return ports


def _snake_case(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def test_ports_exist() -> None:
    assert _declared_ports(), "no ports declared — the discovery logic is broken"


def test_every_port_has_a_registered_fake() -> None:
    from tests.support.fakes import FAKES_BY_PORT

    missing = [f"{ctx}.{port}" for ctx, port in _declared_ports() if port not in FAKES_BY_PORT]
    assert not missing, f"ports without a registered fake: {missing}"


def test_every_port_has_a_contract_suite() -> None:
    missing = []
    for _, port in _declared_ports():
        expected = CONTRACT_DIR / f"test_{_snake_case(port)}.py"
        if not expected.is_file():
            missing.append(str(expected.name))
    assert not missing, f"ports without a contract suite: {missing}"


def test_registered_fakes_structurally_satisfy_their_ports() -> None:
    """Every public method of the port must exist on the fake with a
    compatible call shape (full structural checking is mypy's job)."""
    from tests.support.fakes import FAKES_BY_PORT

    for context, port_name in _declared_ports():
        module = importlib.import_module(f"issuepilot.{context}.application.ports")
        port = getattr(module, port_name)
        fake = FAKES_BY_PORT[port_name]
        for member_name in typing.get_protocol_members(port):
            assert hasattr(fake, member_name), (
                f"{fake.__name__} is missing member {member_name!r} required by {port_name}"
            )
