# Integration tests: CLI-binary resolution from a real pyproject.toml on disk.

from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.core.rules.test_quality import _shared
from axm_audit.core.rules.test_quality._shared import load_project_scripts

pytestmark = pytest.mark.integration

AXM_TOOLS_ONLY = (
    "[project]\n"
    'name = "pkg"\n'
    'version = "0.1.0"\n'
    "\n"
    '[project.entry-points."axm.tools"]\n'
    'audit = "axm_audit.tools:AuditTool"\n'
)

BOTH_TABLES = (
    "[project]\n"
    'name = "pkg"\n'
    'version = "0.1.0"\n'
    "\n"
    "[project.scripts]\n"
    'axm-audit = "axm_audit.cli:main"\n'
    "\n"
    '[project.entry-points."axm.tools"]\n'
    'audit = "axm_audit.tools:AuditTool"\n'
)


def _load_cli_binaries(pkg_root: Path) -> set[str]:
    # Reach the new reader through the module namespace so the missing symbol
    # surfaces as a call-phase assertion, not a collection error.
    load = getattr(_shared, "load_cli_binaries", None)
    assert load is not None, "load_cli_binaries is not implemented"
    binaries: set[str] = load(pkg_root)
    return binaries


def test_axm_tools_only_package_resolves_generic_binary(tmp_path: Path) -> None:
    # AC4: an axm.tools-only package on disk resolves to the axm binary.
    (tmp_path / "pyproject.toml").write_text(AXM_TOOLS_ONLY, encoding="utf-8")

    assert _load_cli_binaries(tmp_path) == {"axm"}
    # guard: load_project_scripts keeps its own (unchanged) semantics
    assert load_project_scripts(tmp_path) == set()


def test_package_declaring_both_tables(tmp_path: Path) -> None:
    # AC4: scripts and axm.tools declared together are unioned on disk.
    (tmp_path / "pyproject.toml").write_text(BOTH_TABLES, encoding="utf-8")

    assert _load_cli_binaries(tmp_path) == {"axm-audit", "axm"}
    # guard: load_project_scripts keeps its own (unchanged) semantics
    assert load_project_scripts(tmp_path) == {"axm-audit"}


def test_missing_or_invalid_pyproject_yields_no_binary(tmp_path: Path) -> None:
    # AC4: an absent or syntactically invalid pyproject yields an empty set,
    # with no exception escaping the reader.
    assert _load_cli_binaries(tmp_path) == set()

    (tmp_path / "pyproject.toml").write_text("[project\nname = ", encoding="utf-8")
    assert _load_cli_binaries(tmp_path) == set()
