"""Versioned prompts loaded from packaged resources.

Every template and schema is content-hashed in ``manifest.json`` and verified
at load. A run records which hashes it used, so a report can be tied to the
exact prompt that produced it — and an accidental edit becomes a loud failure
rather than a silent change in behaviour.

Templates render in a sandboxed Jinja environment with no filesystem loader,
so a template cannot pull in anything that is not packaged here.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources
from typing import Any, Final

from jinja2 import DictLoader, Environment, StrictUndefined

from issuepilot.shared_kernel.errors import InternalError
from issuepilot.shared_kernel.hashing import sha256_hex

_PACKAGE: Final = "issuepilot.prompts"
_MANIFEST: Final = "manifest.json"

REACT_STEP: Final = "react_step@v1"
REPORT: Final = "report@v1"


@dataclass(frozen=True, slots=True)
class Prompt:
    name: str
    version: str
    template_hash: str
    schema_hash: str
    schema: dict[str, Any]
    template_source: str

    def render(self, **context: Any) -> str:
        environment = Environment(
            loader=DictLoader({self.name: self.template_source}),
            undefined=StrictUndefined,
            autoescape=False,  # noqa: S701 - the output is a prompt, not markup
            keep_trailing_newline=True,
        )
        return environment.get_template(self.name).render(**context)


class PromptRegistry:
    """Loads and caches prompts, verifying their recorded content hashes."""

    def __init__(self) -> None:
        self._cache: dict[str, Prompt] = {}
        self._manifest = self._load_manifest()

    @staticmethod
    def _load_manifest() -> dict[str, dict[str, str]]:
        raw = resources.files(_PACKAGE).joinpath(_MANIFEST).read_text(encoding="utf-8")
        loaded: dict[str, dict[str, str]] = json.loads(raw)
        return loaded

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._manifest))

    def get(self, name: str) -> Prompt:
        cached = self._cache.get(name)
        if cached is not None:
            return cached

        entry = self._manifest.get(name)
        if entry is None:
            raise InternalError(f"unknown prompt {name!r}")

        template = self._read(entry["template"])
        schema_text = self._read(entry["schema"])
        self._verify(name, "template", template, entry["template_sha256"])
        self._verify(name, "schema", schema_text, entry["schema_sha256"])

        prompt = Prompt(
            name=name,
            version=entry["version"],
            template_hash=entry["template_sha256"],
            schema_hash=entry["schema_sha256"],
            schema=json.loads(schema_text),
            template_source=template,
        )
        self._cache[name] = prompt
        return prompt

    @staticmethod
    def _read(relative: str) -> str:
        return resources.files(_PACKAGE).joinpath(relative).read_text(encoding="utf-8")

    @staticmethod
    def _verify(name: str, kind: str, content: str, expected: str) -> None:
        actual = sha256_hex(content.encode("utf-8"))
        if actual != expected:
            raise InternalError(
                f"{kind} for prompt {name!r} does not match its recorded hash",
                remediation="regenerate prompts/manifest.json after editing a prompt",
            )
