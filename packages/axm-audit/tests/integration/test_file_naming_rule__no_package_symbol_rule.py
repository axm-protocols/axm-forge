"""Integration tests asserting FileNamingRule plugs into the audit pipeline."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.integration._helpers import _PYPROJECT

pytestmark = pytest.mark.integration


def _seed_pkg(project: Path) -> None:
    (project / "src" / "mypkg").mkdir(parents=True, exist_ok=True)
    (project / "src" / "mypkg" / "__init__.py").write_text("class Rule:\n    pass\n")
    (project / "pyproject.toml").write_text(_PYPROJECT)


def test_no_overlap_with_no_package_symbol(tmp_path: Path) -> None:
    """AC11 — NAME_MISMATCH and NO_PACKAGE_SYMBOL are orthogonal.

    A file whose name diverges from its canonical but DOES exercise the
    package should be flagged by FILE_NAMING and ignored by
    NO_PACKAGE_SYMBOL.
    """
    from axm_audit.core.rules.test_quality.file_naming import FileNamingRule
    from axm_audit.core.rules.test_quality.no_package_symbol import (
        NoPackageSymbolRule,
    )

    project = tmp_path / "proj"
    _seed_pkg(project)
    (project / "tests" / "integration").mkdir(parents=True)
    (project / "tests" / "integration" / "test_unexpected.py").write_text(
        "from mypkg import Rule\n\ndef test_x():\n    Rule()\n"
    )

    naming = FileNamingRule().check(project)
    no_sym = NoPackageSymbolRule().check(project)

    naming_findings = list(naming.details.get("findings", [])) if naming.details else []
    no_sym_findings = list(no_sym.details.get("findings", [])) if no_sym.details else []

    assert any(f["verdict"] == "NAME_MISMATCH" for f in naming_findings), (
        "FILE_NAMING should flag the divergent name"
    )
    assert no_sym_findings == [], (
        "NO_PACKAGE_SYMBOL must not flag a test that exercises the package"
    )
