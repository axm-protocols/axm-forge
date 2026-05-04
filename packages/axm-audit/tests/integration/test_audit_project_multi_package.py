from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from axm_audit.core.auditor import audit_project

pytestmark = pytest.mark.integration


def _make_pkg(
    root: Path,
    name: str,
    files: dict[str, str],
) -> Path:
    pkg_src = root / "packages" / name / "src" / name.replace("-", "_")
    pkg_src.mkdir(parents=True)
    (pkg_src / "__init__.py").write_text("")
    for fname, content in files.items():
        (pkg_src / fname).write_text(textwrap.dedent(content))
    pyproject = root / "packages" / name / "pyproject.toml"
    pyproject.write_text(
        textwrap.dedent(
            f"""
            [project]
            name = "{name}"
            version = "0.0.0"
            requires-python = ">=3.12"
            """
        )
    )
    return pkg_src


def _make_single_pkg(root: Path, files: dict[str, str]) -> Path:
    src = root / "src" / "foo"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    for fname, content in files.items():
        (src / fname).write_text(textwrap.dedent(content))
    (root / "pyproject.toml").write_text(
        textwrap.dedent(
            """
            [project]
            name = "foo"
            version = "0.0.0"
            requires-python = ">=3.12"
            """
        )
    )
    return src


def test_audit_project_multi_package_aggregates_lint_violations(tmp_path: Path) -> None:
    _make_pkg(tmp_path, "pkg-broken", {"bad.py": "def f():\n    x = 1\n    return 0\n"})
    _make_pkg(tmp_path, "pkg-clean", {"ok.py": "def f() -> int:\n    return 0\n"})

    result = audit_project(tmp_path, category="lint")
    failed = [c for c in result.checks if not c.passed and "LINT" in c.rule_id]
    assert failed, "expected at least one failed lint check"
    text = " ".join((c.message or "") + " " + str(c.details or "") for c in failed)
    assert "pkg-broken" in text


def test_audit_project_multi_package_aggregates_type_violations(tmp_path: Path) -> None:
    _make_pkg(
        tmp_path,
        "pkg-typebad",
        {"bad.py": "def f(x: int) -> str:\n    return x\n"},
    )
    _make_pkg(tmp_path, "pkg-clean", {"ok.py": "def f() -> int:\n    return 0\n"})

    result = audit_project(tmp_path, category="type")
    failed = [c for c in result.checks if not c.passed and "TYPE" in c.rule_id]
    assert failed, "expected a failed type check"
    text = " ".join((c.message or "") + " " + str(c.details or "") for c in failed)
    assert "pkg-typebad" in text


def test_audit_project_single_package_unchanged(tmp_path: Path) -> None:
    _make_single_pkg(tmp_path, {"ok.py": "def f() -> int:\n    return 0\n"})
    result = audit_project(tmp_path, category="lint")
    lint_failed = [
        c for c in result.checks if not c.passed and c.rule_id == "QUALITY_LINT"
    ]
    assert lint_failed == []


def test_audit_project_no_layout_short_circuits(tmp_path: Path) -> None:
    result = audit_project(tmp_path)
    src_checks = [c for c in result.checks if c.message == "src/ directory not found"]
    assert src_checks, "expected src-aware rules to short-circuit"
    assert all(c.passed for c in src_checks)


def test_audit_project_real_axm_nexus_surfaces_mypy_errors(tmp_path: Path) -> None:
    nexus = Path("/Users/gabriel/Documents/Code/python/axm-workspaces/axm-nexus")
    if not nexus.exists():
        pytest.skip("axm-nexus workspace not available")
    result = audit_project(nexus, category="type")
    failed = [c for c in result.checks if not c.passed and "TYPE" in c.rule_id]
    if not failed:
        pytest.skip("axm-nexus mypy debt has been cleared — nothing to verify")
    text = " ".join((c.message or "") + " " + str(c.details or "") for c in failed)
    assert "axm-engine" in text or "axm_engine" in text
