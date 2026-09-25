"""In-repo stand-in for the Learning scaffold provider.

``axm-init`` no longer ships Learning templates or rules: the real provider
lives in ``axm-learning`` and is discovered through the
``axm.scaffold_providers`` entry point. Forge's own suite must stay runnable
without that downstream package, so it exercises its routing and orchestration
against this fake, which honours the same hook contract (``layers``,
``finalize``, domain declaration and conflict, profile registration under the
shared root lock, profile check) with deliberately minimal templates.

Learning's actual templates and rules are tested in ``axm-learning``.
"""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field
from importlib.metadata import EntryPoint
from pathlib import Path
from unittest.mock import Mock

import pytest

from axm_init import scaffolding
from axm_init.core.templates import TemplateLayer, TemplateType, template_chain
from axm_init.models.check import CheckResult
from axm_init.scaffolding import ScaffoldRequest, target_root_lock

__all__ = ["FakeLearningProvider", "install_fake_learning_provider"]

_TEMPLATES = Path(__file__).parent / "fixtures" / "learning_provider"


def _declared_domain(metadata_path: Path) -> str | None:
    if not metadata_path.is_file():
        return None
    document = tomllib.loads(metadata_path.read_text(encoding="utf-8"))
    domain = document.get("tool", {}).get("axm-init", {}).get("learning", {})
    value = domain.get("domain") if isinstance(domain, dict) else None
    return value if isinstance(value, str) else None


def _conflict(existing: str, requested: str) -> ValueError:
    return ValueError(
        "learning profile domain conflict: "
        f"existing {existing!r}, requested {requested!r}"
    )


@dataclass
class FakeLearningProvider:
    """Minimal Learning provider recording every hook invocation."""

    calls: list[tuple[str, tuple[object, ...]]] = field(default_factory=list)

    def layers(self, request: ScaffoldRequest) -> tuple[TemplateLayer, ...]:
        """Return the base Python layer plus a tiny overlay, like Learning."""
        self.calls.append(("layers", (request,)))
        overlay = TemplateLayer(
            name="learning",
            path=_TEMPLATES / ("member" if request.member else "overlay"),
            data={},
        )
        if request.member or request.existing:
            return (overlay,)
        base = template_chain(TemplateType.STANDALONE, request.framework, member=False)[
            0
        ]
        return (TemplateLayer(name="base", path=base.path, data=base.data), overlay)

    def finalize(
        self, request: ScaffoldRequest, destination: Path, data: Mapping[str, object]
    ) -> None:
        """Register the profile once rendering succeeded."""
        self.calls.append(("finalize", (request, destination)))
        module_name = str(data.get("package_name", "")).replace("-", "_")
        self.register_learning_profile(
            destination, str(data.get("domain") or module_name), module_name
        )

    def declared_learning_domain(
        self, root: Path, requested_domain: str | None = None
    ) -> str | None:
        """Read the declared domain and refuse a conflicting request."""
        self.calls.append(("declared_learning_domain", (root, requested_domain)))
        with target_root_lock(root):
            existing = _declared_domain(root / "pyproject.toml")
        if existing and requested_domain and existing != requested_domain:
            raise _conflict(existing, requested_domain)
        return existing

    def merge_learning_metadata(
        self, metadata: str, domain: str, module_name: str
    ) -> str:
        """Add the Learning profile table to *metadata*."""
        self.calls.append(("merge_learning_metadata", (domain, module_name)))
        if "learning" in tomllib.loads(metadata).get("tool", {}).get("axm-init", {}):
            return metadata
        profile = f'[tool.axm-init.learning]\nschema_version = 1\ndomain = "{domain}"\n'
        return f"{metadata.rstrip()}\n\n{profile}"

    def register_learning_profile(
        self, root: Path, domain: str, module_name: str
    ) -> None:
        """Merge the profile under the root lock shared with protocol writes."""
        self.calls.append(("register_learning_profile", (root, domain, module_name)))
        with target_root_lock(root):
            metadata_path = root / "pyproject.toml"
            existing = _declared_domain(metadata_path)
            if existing and existing != domain:
                raise _conflict(existing, domain)
            merged = self.merge_learning_metadata(
                metadata_path.read_text(encoding="utf-8"), domain, module_name
            )
            metadata_path.write_text(merged, encoding="utf-8")

    def check_learning_profile(self, root: Path) -> CheckResult:
        """Pass when a domain is declared."""
        self.calls.append(("check_learning_profile", (root,)))
        domain = _declared_domain(root / "pyproject.toml")
        return CheckResult(
            name="learning.learning_profile",
            category="learning",
            passed=domain is not None,
            weight=1,
            message=f"learning profile: {domain}",
            details=[],
            fix="Declare [tool.axm-init.learning].",
        )


def install_fake_learning_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> FakeLearningProvider:
    """Make ``learning`` resolve to a fresh fake; other kinds stay real."""
    provider = FakeLearningProvider()
    entry = Mock(spec=EntryPoint)
    entry.name = "learning"
    entry.load.return_value = Mock(return_value=provider)
    real_entry_points = scaffolding.entry_points

    def entry_points(*, group: str, name: str) -> list[object]:
        if name == "learning":
            return [entry]
        return list(real_entry_points(group=group, name=name))

    monkeypatch.setattr(scaffolding, "entry_points", entry_points)
    return provider
