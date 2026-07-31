"""Unit tests for ``check_tests_dir`` (relocated from integration)."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_init.checks.structure import check_tests_dir


class TestCheckTestsDirPyramid:
    @pytest.mark.parametrize(
        ("fixture_name", "expected"),
        [
            pytest.param("gold_project", True, id="pass"),
            pytest.param("empty_project", False, id="fail"),
        ],
    )
    def test_tests_dir(
        self,
        request: pytest.FixtureRequest,
        fixture_name: str,
        expected: bool,
    ) -> None:
        """AC1: the existing legacy-suite fixtures retain their contract."""
        project: Path = request.getfixturevalue(fixture_name)
        r = check_tests_dir(project)
        assert r.passed is expected

    def test_namespaced_suite_is_accepted(self, tmp_path: Path) -> None:
        """AC1: a normalized package-specific suite replaces hardcoded tests/."""
        project = tmp_path / "demo-pkg"
        suite = project / "tests_demo_pkg"
        for level in ("unit", "integration", "e2e"):
            (suite / level).mkdir(parents=True)
        (suite / "unit" / "test_demo.py").write_text("def test_demo() -> None: pass\n")

        result = check_tests_dir(project)

        assert result.passed is True

    def test_missing_suite_names_package_specific_directory(
        self, tmp_path: Path
    ) -> None:
        """AC1: a missing suite reports the canonical package-specific name."""
        project = tmp_path / "demo-pkg"
        project.mkdir()

        result = check_tests_dir(project)

        assert result.passed is False
        assert "tests_demo_pkg" in result.message
        assert "tests_demo_pkg" in result.fix
