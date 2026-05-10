from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any

import pytest

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


class TestDep002FalsePositiveFiltered:
    """DEP002 for packages reachable via entry-points or optional-deps."""

    # noqa: entry-point and optional-dep false positives should be filtered

    @pytest.mark.parametrize(
        "pyproject_content",
        [
            pytest.param(
                """\
                [project]
                name = "test-pkg"
                dependencies = ["axm-init"]

                [project.entry-points."axm.tools"]
                init = "axm_init.tool:InitTool"
                """,
                id="entry_point_dep_filtered",
            ),
            pytest.param(
                """\
                [project]
                name = "test-pkg"
                dependencies = []

                [project.optional-dependencies]
                init = ["axm-init"]
                """,
                id="optional_dep_filtered",
            ),
        ],
    )
    def test_dep002_false_positive_filtered(
        self, tmp_path: Path, mocker: Any, pyproject_content: str
    ) -> None:
        _make_pyproject(tmp_path, pyproject_content)
        mocker.patch(
            f"{MODULE}.run_deptry",
            return_value=[
                _dep_issue("DEP002", "axm_init"),
            ],
        )
        rule = DependencyHygieneRule()
        result = rule.check(tmp_path)
        assert result.passed
        assert result.details is not None
        assert result.details["issue_count"] == 0


class TestNonDep002CodesPreserved:
    """DEP001/DEP003 must NOT be filtered for entry-point/optional-dep pkgs."""

    @pytest.mark.parametrize(
        ("dep_code", "pyproject_content"),
        [
            pytest.param(
                "DEP001",
                """\
                [project]
                name = "test-pkg"
                dependencies = []

                [project.entry-points."axm.tools"]
                init = "axm_init.tool:InitTool"
                """,
                id="dep001_entry_point_not_filtered",
            ),
            pytest.param(
                "DEP003",
                """\
                [project]
                name = "test-pkg"
                dependencies = []

                [project.optional-dependencies]
                init = ["axm-init"]
                """,
                id="dep003_optional_dep_not_filtered",
            ),
        ],
    )
    def test_non_dep002_code_preserved(
        self, tmp_path: Path, mocker: Any, dep_code: str, pyproject_content: str
    ) -> None:
        _make_pyproject(tmp_path, pyproject_content)
        mocker.patch(
            f"{MODULE}.run_deptry",
            return_value=[
                _dep_issue(dep_code, "axm_init"),
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
            f"{MODULE}.run_deptry",
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
            f"{MODULE}.run_deptry",
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
            f"{MODULE}.run_deptry",
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
            f"{MODULE}.run_deptry",
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
            f"{MODULE}.run_deptry",
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
