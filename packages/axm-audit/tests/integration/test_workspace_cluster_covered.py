"""Workspace doublon is covered by ``duplicate_code`` after the dedicated rule is gone.

AXM-2177 retires the ad-hoc ``ARCH_UV_WORKSPACE_LOCALITY`` rule. These tests
pin the contract: (1) the generic ``ARCH_DUPLICATION`` detector catches a
``[tool.uv.workspace]`` parsing cluster (the pre-requisite that justified the
removal), and (2) the dedicated rule is gone from the architecture registry
while the architecture category still runs green.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from axm_audit.core.auditor import audit_project, get_rules_for_category

# A real copy-paste of a workspace-resolution helper: the same function (same
# name, same body, >= 6 lines) duplicated across two modules — exactly the
# residual ``resolve_workspace`` copies (e.g. axm-warden) that the dedicated
# rule used to guard. ``ARCH_DUPLICATION`` keys on the normalised function
# body, so identical copy-pastes form one clone group.
_WORKSPACE_HELPER = textwrap.dedent(
    """
    import tomllib
    from pathlib import Path


    def resolve_workspace(root: Path) -> list[str]:
        pyproject = root / "pyproject.toml"
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        tool = data.get("tool", {})
        uv = tool.get("uv", {})
        members = uv.get("workspace", {}).get("members", [])
        return members
    """
)


def _write_corpus(root: Path, *modules: str) -> None:
    """Lay out a minimal ``src/pkg`` corpus with one module per body in *modules*."""
    pkg = root / "src" / "pkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    for i, body in enumerate(modules):
        (pkg / f"mod_{i}.py").write_text(body, encoding="utf-8")
    (root / "pyproject.toml").write_text(
        '[project]\nname = "pkg"\nversion = "0.1"\n', encoding="utf-8"
    )


@pytest.mark.integration
def test_duplicate_code_detects_workspace_cluster(tmp_path: Path) -> None:
    """AC1, AC4: ``ARCH_DUPLICATION`` flags a 2-copy workspace-parsing cluster.

    Pre-requisite that justifies retiring the dedicated rule: the generic
    duplicate-code detector already catches the residual ``resolve_workspace``
    copy-paste cluster. If this fails, the dedicated rule must NOT be removed.
    """
    _write_corpus(tmp_path, _WORKSPACE_HELPER, _WORKSPACE_HELPER)

    result = audit_project(tmp_path, category="architecture")

    dup = next(
        (c for c in result.checks if c.rule_id == "ARCH_DUPLICATION"),
        None,
    )
    assert dup is not None, "duplicate_code must run under architecture"
    assert dup.passed is False, "the workspace cluster must be flagged"
    assert dup.details is not None
    assert dup.details["dup_count"] >= 1


@pytest.mark.integration
def test_arch_rule_removed(tmp_path: Path) -> None:
    """AC2, AC3: the dedicated locality rule is gone; architecture stays green.

    The architecture registry must no longer expose
    ``ARCH_UV_WORKSPACE_LOCALITY``, and a clean corpus (no copy-paste, no
    forbidden parsing) must yield an all-passing architecture category.
    """
    rule_ids = {r.rule_id for r in get_rules_for_category("architecture")}
    assert "ARCH_UV_WORKSPACE_LOCALITY" not in rule_ids

    clean = textwrap.dedent(
        """
        def add(a: int, b: int) -> int:
            return a + b
        """
    )
    _write_corpus(tmp_path, clean)

    result = audit_project(tmp_path, category="architecture")

    assert all(c.rule_id != "ARCH_UV_WORKSPACE_LOCALITY" for c in result.checks), (
        "the removed rule must not surface in audit output"
    )
    assert all(c.passed for c in result.checks), "architecture must stay green"
