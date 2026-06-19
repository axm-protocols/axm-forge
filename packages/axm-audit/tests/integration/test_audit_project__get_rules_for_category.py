"""The dedicated locality rule is gone; architecture stays green (AXM-2177).

AXM-2177 retires the ad-hoc ``ARCH_UV_WORKSPACE_LOCALITY`` rule. This test
pins the contract that the dedicated rule is gone from the architecture
registry while the architecture category still runs green.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from axm_audit.core.auditor import audit_project, get_rules_for_category


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
