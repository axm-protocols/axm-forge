from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import call

import pytest
from pytest_mock import MockerFixture

from axm_audit.core.rules.dependencies import (
    DependencyAuditRule,
    DependencyHygieneRule,
    resolve_workspace_members,
)

MOD = "axm_audit.core.rules.dependencies"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def rule() -> DependencyHygieneRule:
    return DependencyHygieneRule()


def _write_pyproject(path: Path, content: str = "") -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "pyproject.toml").write_text(content)


def _workspace_toml(*member_patterns: str) -> str:
    members = ", ".join(f'"{p}"' for p in member_patterns)
    return f"[tool.uv.workspace]\nmembers = [{members}]\n"


def _make_issue(
    code: str = "DEP001",
    module: str = "foo",
    message: str = "missing",
) -> dict[str, Any]:
    return {"error": {"code": code, "message": message}, "module": module}


# ---------------------------------------------------------------------------
# _resolve_workspace_members — unit tests
# ---------------------------------------------------------------------------


class TestResolveWorkspaceMembers:
    @pytest.mark.parametrize(
        ("member_patterns", "package_paths", "expected_names"),
        [
            pytest.param(
                ("packages/*",),
                ("packages/pkg-a", "packages/pkg-b"),
                ["pkg-a", "pkg-b"],
                id="single_pattern",
            ),
            pytest.param(
                ("packages/*", "libs/*"),
                ("packages/pkg-a", "libs/lib-x"),
                ["lib-x", "pkg-a"],
                id="multiple_patterns",
            ),
        ],
    )
    def test_resolve_returns_member_names(
        self,
        tmp_path: Path,
        member_patterns: tuple[str, ...],
        package_paths: tuple[str, ...],
        expected_names: list[str],
    ) -> None:
        """Workspace globs resolve to sub-dirs with pyproject.toml."""
        _write_pyproject(tmp_path, _workspace_toml(*member_patterns))
        for pkg in package_paths:
            _write_pyproject(tmp_path / pkg)

        result = resolve_workspace_members(tmp_path)

        assert result is not None
        assert sorted(p.name for p in result) == expected_names

    def test_resolve_workspace_members_no_workspace(self, tmp_path: Path) -> None:
        """Non-workspace pyproject returns None."""
        _write_pyproject(tmp_path, '[project]\nname = "solo"\n')

        result = resolve_workspace_members(tmp_path)

        assert result is None

    def test_resolve_workspace_members_empty_glob(self, tmp_path: Path) -> None:
        """Workspace glob matching no directories returns empty list."""
        _write_pyproject(tmp_path, _workspace_toml("packages/*"))
        (tmp_path / "packages").mkdir()

        result = resolve_workspace_members(tmp_path)

        assert result == []

    def test_resolve_workspace_members_skips_no_pyproject(self, tmp_path: Path) -> None:
        """Dirs without pyproject.toml are silently skipped."""
        _write_pyproject(tmp_path, _workspace_toml("packages/*"))
        _write_pyproject(tmp_path / "packages" / "has-pyproject")
        (tmp_path / "packages" / "no-pyproject").mkdir(parents=True)

        result = resolve_workspace_members(tmp_path)

        assert result is not None
        assert len(result) == 1
        assert result[0].name == "has-pyproject"


# ---------------------------------------------------------------------------
# DependencyHygieneRule.check — workspace integration
# ---------------------------------------------------------------------------


class TestDependencyHygieneRule:
    def test_hygiene_workspace_aggregates(
        self, rule: DependencyHygieneRule, tmp_path: Path, mocker: MockerFixture
    ) -> None:
        """Workspace mode aggregates issues from all members."""
        member_a = tmp_path / "packages" / "a"
        member_b = tmp_path / "packages" / "b"

        mocker.patch(
            f"{MOD}.resolve_workspace_members",
            return_value=[member_a, member_b],
        )
        mocker.patch(
            f"{MOD}.run_deptry",
            side_effect=[
                [_make_issue("DEP001", "x"), _make_issue("DEP003", "y")],
                [_make_issue("DEP002", "z")],
            ],
        )
        mocker.patch(f"{MOD}._filter_false_positives", side_effect=lambda i, _p: i)

        result = rule.check(tmp_path)

        assert result.details is not None
        assert result.details["issue_count"] == 3
        assert result.score == 70

    def test_hygiene_workspace_filters_per_member(
        self, rule: DependencyHygieneRule, tmp_path: Path, mocker: MockerFixture
    ) -> None:
        """Filtering is applied per-member with the member path."""
        member_a = tmp_path / "packages" / "a"
        member_b = tmp_path / "packages" / "b"
        issue_a = _make_issue("DEP002", "entry-dep")
        issue_b = _make_issue("DEP001", "real-missing")

        mocker.patch(
            f"{MOD}.resolve_workspace_members",
            return_value=[member_a, member_b],
        )
        mocker.patch(
            f"{MOD}.run_deptry",
            side_effect=[[issue_a], [issue_b]],
        )
        mock_filter = mocker.patch(
            f"{MOD}._filter_false_positives",
            side_effect=[[], [issue_b]],
        )

        result = rule.check(tmp_path)

        assert result.details is not None
        assert result.details["issue_count"] == 1
        mock_filter.assert_has_calls(
            [
                call([issue_a], member_a),
                call([issue_b], member_b),
            ]
        )

    def test_hygiene_single_package_unchanged(
        self, rule: DependencyHygieneRule, tmp_path: Path, mocker: MockerFixture
    ) -> None:
        """Non-workspace project uses existing single-package path."""
        mocker.patch(f"{MOD}.resolve_workspace_members", return_value=None)
        mocker.patch(
            f"{MOD}.run_deptry",
            return_value=[_make_issue("DEP001", "a"), _make_issue("DEP003", "b")],
        )
        mocker.patch(f"{MOD}._filter_false_positives", side_effect=lambda i, _p: i)

        result = rule.check(tmp_path)

        assert result.details is not None
        assert result.details["issue_count"] == 2
        assert result.score == 80

    def test_workspace_one_member_crashes(
        self, rule: DependencyHygieneRule, tmp_path: Path, mocker: MockerFixture
    ) -> None:
        """If one member's deptry fails, partial results from others are kept."""
        member_a = tmp_path / "packages" / "a"
        member_b = tmp_path / "packages" / "b"

        mocker.patch(
            f"{MOD}.resolve_workspace_members",
            return_value=[member_a, member_b],
        )
        mocker.patch(
            f"{MOD}.run_deptry",
            side_effect=[
                RuntimeError("deptry crashed"),
                [_make_issue("DEP001", "ok")],
            ],
        )
        mocker.patch(f"{MOD}._filter_false_positives", side_effect=lambda i, _p: i)

        result = rule.check(tmp_path)

        assert result.details is not None
        assert result.details["issue_count"] == 1


class TestDependencyAuditRule:
    @pytest.fixture
    def rule(self) -> DependencyAuditRule:
        return DependencyAuditRule()

    @pytest.fixture
    def project_path(self, tmp_path: Path) -> Path:
        return tmp_path

    def test_check_excludes_pip_env_tool(
        self, mocker: Any, rule: DependencyAuditRule, project_path: Path
    ) -> None:
        _patch_audit(
            mocker,
            [
                {
                    "name": "pip",
                    "version": "26.0.1",
                    "vulns": [{"id": "CVE-2026-3219", "fix_versions": []}],
                }
            ],
        )

        result = rule.check(project_path)

        assert result.details is not None
        assert result.details["vuln_count"] == 0
        assert result.passed is True
        assert result.details["top_vulns"] == []

    def test_check_keeps_real_vuln_alongside_env_tool(
        self, mocker: Any, rule: DependencyAuditRule, project_path: Path
    ) -> None:
        _patch_audit(
            mocker,
            [
                {
                    "name": "pip",
                    "version": "26.0.1",
                    "vulns": [{"id": "CVE-2026-3219", "fix_versions": []}],
                },
                {
                    "name": "requests",
                    "version": "2.20.0",
                    "vulns": [{"id": "CVE-2018-18074", "fix_versions": ["2.20.1"]}],
                },
            ],
        )

        result = rule.check(project_path)

        assert result.details is not None
        assert result.details["vuln_count"] == 1
        assert result.details["top_vulns"][0]["name"] == "requests"

    @pytest.mark.parametrize(
        "pkg_name",
        ["pip", "setuptools", "wheel", "uv", "pip-audit", "PIP", "Setuptools"],
    )
    def test_check_excludes_each_env_tool(
        self,
        mocker: Any,
        rule: DependencyAuditRule,
        project_path: Path,
        pkg_name: str,
    ) -> None:
        _patch_audit(
            mocker,
            [
                {
                    "name": pkg_name,
                    "version": "1.0.0",
                    "vulns": [{"id": "CVE-XXXX-0001", "fix_versions": []}],
                }
            ],
        )

        result = rule.check(project_path)

        assert result.details is not None
        assert result.details["vuln_count"] == 0

    def test_check_passes_through_unknown_package(
        self, mocker: Any, rule: DependencyAuditRule, project_path: Path
    ) -> None:
        _patch_audit(
            mocker,
            [
                {
                    "name": "numpy",
                    "version": "1.0.0",
                    "vulns": [{"id": "CVE-XXXX-0002", "fix_versions": []}],
                }
            ],
        )

        result = rule.check(project_path)

        assert result.details is not None
        assert result.details["vuln_count"] == 1


def _patch_audit(mocker: Any, payload: list[dict[str, Any]]) -> None:
    mocker.patch(f"{MODULE}._run_pip_audit", return_value=payload)


MODULE = "axm_audit.core.rules.dependencies"
