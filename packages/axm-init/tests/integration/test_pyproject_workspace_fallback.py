"""Tests for pyproject tooling checks with workspace root fallback.

Verifies that check functions (ruff, ruff_rules, mypy, pytest, coverage)
resolve config from the workspace root when the member package lacks it.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

from axm_init.checks.pyproject import (
    check_pyproject_coverage,
    check_pyproject_mypy,
    check_pyproject_pytest,
    check_pyproject_ruff,
    check_pyproject_ruff_rules,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_toml(path: Path, content: str) -> None:
    """Write a TOML file, creating parent dirs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content))


def _make_workspace(tmp_path: Path, root_toml: str, member_toml: str = "") -> Path:
    """Create a workspace layout and return the member path.

    Layout:
        tmp_path/pyproject.toml          <- workspace root (with [tool.uv.workspace])
        tmp_path/packages/pkg/pyproject.toml  <- member
    """
    _write_toml(
        tmp_path / "pyproject.toml",
        root_toml,
    )
    member = tmp_path / "packages" / "pkg"
    member.mkdir(parents=True, exist_ok=True)
    if member_toml:
        _write_toml(member / "pyproject.toml", member_toml)
    else:
        # Minimal member pyproject with no tool sections
        _write_toml(
            member / "pyproject.toml",
            """\
            [project]
            name = "pkg"
            version = "0.1.0"
            """,
        )
    return member


ROOT_WORKSPACE_HEADER = """\
[project]
name = "workspace"
version = "0.0.0"

[tool.uv.workspace]
members = ["packages/*"]
"""


# ---------------------------------------------------------------------------
# Unit tests from test_spec
# ---------------------------------------------------------------------------


class TestRuffRulesFromWorkspaceRoot:
    """test_ruff_rules_from_workspace_root.

    Workspace root has ruff rules, member does not.
    """

    def test_passes_when_rules_in_workspace_root(self, tmp_path: Path) -> None:
        root_toml = ROOT_WORKSPACE_HEADER + textwrap.dedent("""\

            [tool.ruff.lint]
            select = ["E", "F", "I", "UP", "B", "S", "BLE", "PLR", "N"]
        """)
        member = _make_workspace(tmp_path, root_toml)
        result = check_pyproject_ruff_rules(member)
        assert result.passed, f"Expected pass, got: {result.details}"


class TestMypyFromWorkspaceRoot:
    """test_mypy_from_workspace_root.

    Workspace root has mypy config, member does not.
    """

    def test_passes_when_mypy_in_workspace_root(self, tmp_path: Path) -> None:
        root_toml = ROOT_WORKSPACE_HEADER + textwrap.dedent("""\

            [tool.mypy]
            strict = true
            pretty = true
            disallow_incomplete_defs = true
            check_untyped_defs = true
        """)
        member = _make_workspace(tmp_path, root_toml)
        result = check_pyproject_mypy(member)
        assert result.passed, f"Expected pass, got: {result.details}"


class TestStandaloneNoFallback:
    """test_standalone_no_fallback.

    Standalone project with no ruff config still fails.
    """

    def test_fails_without_workspace(self, tmp_path: Path) -> None:
        _write_toml(
            tmp_path / "pyproject.toml",
            """\
            [project]
            name = "standalone"
            version = "0.1.0"
            """,
        )
        result = check_pyproject_ruff(tmp_path)
        assert not result.passed


class TestMemberOverrideWins:
    """test_member_override_wins: member config takes precedence over workspace root."""

    def test_member_ruff_overrides_root(self, tmp_path: Path) -> None:
        root_toml = ROOT_WORKSPACE_HEADER + textwrap.dedent("""\

            [tool.ruff.lint]
            select = ["E", "F"]
        """)
        # Member defines its own ruff rules that include all required
        member_toml = textwrap.dedent("""\
            [project]
            name = "pkg"
            version = "0.1.0"

            [tool.ruff.lint]
            select = ["E", "F", "I", "UP", "B", "S", "BLE", "PLR", "N"]
        """)
        member = _make_workspace(tmp_path, root_toml, member_toml)
        result = check_pyproject_ruff_rules(member)
        assert result.passed, f"Member override should win, got: {result.details}"


# ---------------------------------------------------------------------------
# Edge cases from test_spec
# ---------------------------------------------------------------------------


class TestWorkspaceRootNoPyproject:
    """Edge: workspace root dir exists but has no pyproject.toml."""

    def test_falls_back_to_member_only(self, tmp_path: Path) -> None:
        """When no workspace root pyproject.toml exists, use member config only."""
        member = tmp_path / "packages" / "pkg"
        member.mkdir(parents=True, exist_ok=True)
        _write_toml(
            member / "pyproject.toml",
            """\
            [project]
            name = "pkg"
            version = "0.1.0"
            """,
        )
        # No workspace root pyproject.toml at all
        result = check_pyproject_ruff(member)
        assert not result.passed  # No ruff config anywhere -> fail


class TestMemberPartialOverride:
    """Edge: member has ruff but not mypy; workspace root has both."""

    def test_ruff_from_member_mypy_from_root(self, tmp_path: Path) -> None:
        root_toml = ROOT_WORKSPACE_HEADER + textwrap.dedent("""\

            [tool.ruff.lint]
            select = ["E", "F"]
            per-file-ignores = { "tests/**" = ["S101"] }

            [tool.ruff.lint.isort]
            known-first-party = ["pkg"]

            [tool.mypy]
            strict = true
            pretty = true
            disallow_incomplete_defs = true
            check_untyped_defs = true
        """)
        # Member overrides ruff only (with full config), no mypy
        member_toml = textwrap.dedent("""\
            [project]
            name = "pkg"
            version = "0.1.0"

            [tool.ruff.lint]
            select = ["E", "F", "I", "UP", "B", "S", "BLE", "PLR", "N"]
            per-file-ignores = { "tests/**" = ["S101"] }

            [tool.ruff.lint.isort]
            known-first-party = ["pkg"]
        """)
        member = _make_workspace(tmp_path, root_toml, member_toml)

        # Ruff uses member config (which has full rules) -> pass
        ruff_result = check_pyproject_ruff(member)
        assert ruff_result.passed, (
            f"Ruff should use member config: {ruff_result.details}"
        )

        # Mypy falls back to workspace root -> pass
        mypy_result = check_pyproject_mypy(member)
        assert mypy_result.passed, (
            f"Mypy should fall back to root: {mypy_result.details}"
        )


# ---------------------------------------------------------------------------
# Additional AC coverage: pytest and coverage from workspace root
# ---------------------------------------------------------------------------


class TestPytestFromWorkspaceRoot:
    """AC4: pytest config resolved from workspace root."""

    def test_passes_when_pytest_in_workspace_root(self, tmp_path: Path) -> None:
        root_toml = ROOT_WORKSPACE_HEADER + textwrap.dedent("""\

            [tool.pytest.ini_options]
            addopts = ["--strict-markers", "--strict-config", "--import-mode=importlib"]
            pythonpath = ["src"]
            filterwarnings = ["error"]
        """)
        member = _make_workspace(tmp_path, root_toml)
        result = check_pyproject_pytest(member)
        assert result.passed, f"Expected pass, got: {result.details}"


class TestCoverageFromWorkspaceRoot:
    """AC5: coverage config resolved from workspace root."""

    def test_passes_when_coverage_in_workspace_root(self, tmp_path: Path) -> None:
        root_toml = ROOT_WORKSPACE_HEADER + textwrap.dedent("""\

            [tool.coverage.run]
            branch = true
            relative_files = true

            [tool.coverage.xml]
            output = "coverage.xml"

            [tool.coverage.report]
            exclude_lines = ["pragma: no cover"]
        """)
        member = _make_workspace(tmp_path, root_toml)
        result = check_pyproject_coverage(member)
        assert result.passed, f"Expected pass, got: {result.details}"


class TestRuffFromWorkspaceRoot:
    """AC1: ruff config (per-file-ignores + known-first-party) from workspace root."""

    def test_passes_when_ruff_in_workspace_root(self, tmp_path: Path) -> None:
        root_toml = ROOT_WORKSPACE_HEADER + textwrap.dedent("""\

            [tool.ruff.lint]
            per-file-ignores = { "tests/**" = ["S101"] }

            [tool.ruff.lint.isort]
            known-first-party = ["pkg"]
        """)
        member = _make_workspace(tmp_path, root_toml)
        result = check_pyproject_ruff(member)
        assert result.passed, f"Expected pass, got: {result.details}"
