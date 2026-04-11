from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any

from axm_audit.core.rules.dependencies import DependencyHygieneRule

MODULE = "axm_audit.core.rules.dependencies"


def _make_pyproject(tmp_path: Path, content: str) -> Path:
    """Write a pyproject.toml and return project path."""
    (tmp_path / "pyproject.toml").write_text(textwrap.dedent(content))
    return tmp_path


def _dep_issue(code: str, module: str, message: str = "") -> dict[str, Any]:
    """Build a deptry issue dict."""
    return {
        "error": {"code": code, "message": message or f"{code} for {module}"},
        "module": module,
    }


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


class TestEntryPointDepsNotReported:
    """DEP002 for packages consumed via entry-points should be filtered."""

    def test_entry_point_deps_filtered(self, tmp_path: Path, mocker: Any) -> None:
        _make_pyproject(
            tmp_path,
            """\
            [project]
            name = "test-pkg"
            dependencies = ["axm-init"]

            [project.entry-points."axm.tools"]
            init = "axm_init.tool:InitTool"
            """,
        )
        mocker.patch(
            f"{MODULE}._run_deptry",
            return_value=[
                _dep_issue("DEP002", "axm_init"),
            ],
        )
        rule = DependencyHygieneRule()
        result = rule.check(tmp_path)
        assert result.passed
        assert result.details is not None
        assert result.details["issue_count"] == 0


class TestOptionalDepsNotReported:
    """DEP002 for packages in optional-dependencies should be filtered."""

    def test_optional_deps_filtered(self, tmp_path: Path, mocker: Any) -> None:
        _make_pyproject(
            tmp_path,
            """\
            [project]
            name = "test-pkg"
            dependencies = []

            [project.optional-dependencies]
            init = ["axm-init"]
            """,
        )
        mocker.patch(
            f"{MODULE}._run_deptry",
            return_value=[
                _dep_issue("DEP002", "axm_init"),
            ],
        )
        rule = DependencyHygieneRule()
        result = rule.check(tmp_path)
        assert result.passed
        assert result.details is not None
        assert result.details["issue_count"] == 0


class TestDep001NotFiltered:
    """DEP001 (missing) must NOT be filtered even for entry-point packages."""

    def test_dep001_preserved(self, tmp_path: Path, mocker: Any) -> None:
        _make_pyproject(
            tmp_path,
            """\
            [project]
            name = "test-pkg"
            dependencies = []

            [project.entry-points."axm.tools"]
            init = "axm_init.tool:InitTool"
            """,
        )
        mocker.patch(
            f"{MODULE}._run_deptry",
            return_value=[
                _dep_issue("DEP001", "axm_init"),
            ],
        )
        rule = DependencyHygieneRule()
        result = rule.check(tmp_path)
        assert result.details is not None
        assert result.details["issue_count"] == 1


class TestDep003NotFiltered:
    """DEP003 (transitive) must NOT be filtered even for extras packages."""

    def test_dep003_preserved(self, tmp_path: Path, mocker: Any) -> None:
        _make_pyproject(
            tmp_path,
            """\
            [project]
            name = "test-pkg"
            dependencies = []

            [project.optional-dependencies]
            init = ["axm-init"]
            """,
        )
        mocker.patch(
            f"{MODULE}._run_deptry",
            return_value=[
                _dep_issue("DEP003", "axm_init"),
            ],
        )
        rule = DependencyHygieneRule()
        result = rule.check(tmp_path)
        assert result.details is not None
        assert result.details["issue_count"] == 1


class TestGenuineUnusedStillReported:
    """DEP002 for packages NOT in entry-points or extras must be reported."""

    def test_genuine_unused_reported(self, tmp_path: Path, mocker: Any) -> None:
        _make_pyproject(
            tmp_path,
            """\
            [project]
            name = "test-pkg"
            dependencies = ["some-unused-lib"]

            [project.entry-points."axm.tools"]
            init = "axm_init.tool:InitTool"
            """,
        )
        mocker.patch(
            f"{MODULE}._run_deptry",
            return_value=[
                _dep_issue("DEP002", "some_unused_lib"),
            ],
        )
        rule = DependencyHygieneRule()
        result = rule.check(tmp_path)
        assert result.details is not None
        assert result.details["issue_count"] == 1


class TestNameNormalization:
    """Hyphenated names in pyproject.toml match underscored deptry modules."""

    def test_hyphen_underscore_normalization(self, tmp_path: Path, mocker: Any) -> None:
        _make_pyproject(
            tmp_path,
            """\
            [project]
            name = "test-pkg"
            dependencies = ["axm-init"]

            [project.entry-points."axm.tools"]
            init = "axm_init.tool:InitTool"
            """,
        )
        mocker.patch(
            f"{MODULE}._run_deptry",
            return_value=[
                _dep_issue("DEP002", "axm_init"),
            ],
        )
        rule = DependencyHygieneRule()
        result = rule.check(tmp_path)
        assert result.details is not None
        assert result.details["issue_count"] == 0


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestNoPyprojectToml:
    """Without pyproject.toml no filtering is applied."""

    def test_no_filtering_without_pyproject(self, tmp_path: Path, mocker: Any) -> None:
        mocker.patch(
            f"{MODULE}._run_deptry",
            return_value=[
                _dep_issue("DEP002", "axm_init"),
            ],
        )
        rule = DependencyHygieneRule()
        result = rule.check(tmp_path)
        assert result.details is not None
        assert result.details["issue_count"] == 1


class TestEmptyEntryPoints:
    """Empty entry-points section means no filtering."""

    def test_empty_entry_points_no_filtering(self, tmp_path: Path, mocker: Any) -> None:
        _make_pyproject(
            tmp_path,
            """\
            [project]
            name = "test-pkg"
            dependencies = ["some-lib"]

            [project.entry-points]
            """,
        )
        mocker.patch(
            f"{MODULE}._run_deptry",
            return_value=[
                _dep_issue("DEP002", "some_lib"),
            ],
        )
        rule = DependencyHygieneRule()
        result = rule.check(tmp_path)
        assert result.details is not None
        assert result.details["issue_count"] == 1


# ---------------------------------------------------------------------------
# Functional: mixed real and false-positive issues
# ---------------------------------------------------------------------------


class TestMixedRealAndFalsePositive:
    """Only false positives filtered; genuine issues remain."""

    def test_mixed_filtering(self, tmp_path: Path, mocker: Any) -> None:
        _make_pyproject(
            tmp_path,
            """\
            [project]
            name = "test-pkg"
            dependencies = ["axm-init", "unused-lib"]

            [project.entry-points."axm.tools"]
            init = "axm_init.tool:InitTool"

            [project.optional-dependencies]
            extra = ["axm-smelt"]
            """,
        )
        mocker.patch(
            f"{MODULE}._run_deptry",
            return_value=[
                _dep_issue("DEP002", "axm_init"),
                _dep_issue("DEP002", "axm_smelt"),
                _dep_issue("DEP002", "unused_lib"),
                _dep_issue("DEP001", "axm_init"),
            ],
        )
        rule = DependencyHygieneRule()
        result = rule.check(tmp_path)
        # axm_init DEP002 filtered (entry-point)
        # axm_smelt DEP002 filtered (optional-dep)
        # unused_lib DEP002 kept (genuine unused)
        # axm_init DEP001 kept (not DEP002)
        assert result.details is not None
        assert result.details["issue_count"] == 2
        modules = [i["module"] for i in result.details["top_issues"]]
        assert "unused_lib" in modules
        assert "axm_init" in modules
        assert "axm_smelt" not in modules
