"""Tests for checks.pyproject — pyproject.toml checks."""

from __future__ import annotations

from pathlib import Path

from axm_init.checks.pyproject import (
    check_pyproject_mypy,
)


class TestCheckPyprojectMypy:
    def test_pass(self, gold_project: Path) -> None:
        r = check_pyproject_mypy(gold_project)
        assert r.passed is True

    def test_fail_missing_section(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
        r = check_pyproject_mypy(tmp_path)
        assert r.passed is False

    def test_fail_partial(self, tmp_path: Path) -> None:
        toml = '[project]\nname="x"\n[tool.mypy]\nstrict = true\n'
        (tmp_path / "pyproject.toml").write_text(toml)
        r = check_pyproject_mypy(tmp_path)
        assert r.passed is False
        assert "pretty" in str(r.details).lower()


class TestCheckPyprojectMypyStrict:
    """Tests for strict=true implication logic in check_pyproject_mypy."""

    def test_mypy_strict_implies_sub_flags(self, tmp_path: Path) -> None:
        """strict=true implies disallow_incomplete_defs & check_untyped_defs."""
        toml = '[project]\nname="x"\n[tool.mypy]\nstrict = true\npretty = true\n'
        (tmp_path / "pyproject.toml").write_text(toml)
        r = check_pyproject_mypy(tmp_path)
        assert r.passed is True
        assert r.weight == 3

    def test_mypy_no_strict_requires_explicit(self, tmp_path: Path) -> None:
        """Without strict, sub-flags must be set explicitly."""
        toml = '[project]\nname="x"\n[tool.mypy]\npretty = true\n'
        (tmp_path / "pyproject.toml").write_text(toml)
        r = check_pyproject_mypy(tmp_path)
        assert r.passed is False
        details = str(r.details).lower()
        assert "strict" in details
        assert "disallow_incomplete_defs" in details
        assert "check_untyped_defs" in details

    def test_mypy_strict_with_override_false(self, tmp_path: Path) -> None:
        """strict=true but sub-flag explicitly false -> check fails."""
        toml = (
            '[project]\nname="x"\n[tool.mypy]\n'
            "strict = true\npretty = true\ncheck_untyped_defs = false\n"
        )
        (tmp_path / "pyproject.toml").write_text(toml)
        r = check_pyproject_mypy(tmp_path)
        assert r.passed is False
        assert "check_untyped_defs" in str(r.details)

    def test_mypy_pretty_not_implied(self, tmp_path: Path) -> None:
        """pretty is NOT implied by strict — must be set explicitly."""
        toml = '[project]\nname="x"\n[tool.mypy]\nstrict = true\n'
        (tmp_path / "pyproject.toml").write_text(toml)
        r = check_pyproject_mypy(tmp_path)
        assert r.passed is False
        assert "pretty" in str(r.details).lower()

    def test_mypy_strict_false_requires_explicit(self, tmp_path: Path) -> None:
        """strict=false does not imply sub-flags."""
        toml = (
            '[project]\nname="x"\n[tool.mypy]\n'
            "strict = false\ndisallow_incomplete_defs = true\n"
            "check_untyped_defs = true\npretty = true\n"
        )
        (tmp_path / "pyproject.toml").write_text(toml)
        r = check_pyproject_mypy(tmp_path)
        assert r.passed is False
        assert "strict" in str(r.details).lower()

    def test_mypy_all_explicit_with_strict(self, tmp_path: Path) -> None:
        """All flags explicit + strict=true — redundant but valid."""
        toml = (
            '[project]\nname="x"\n[tool.mypy]\n'
            "strict = true\npretty = true\n"
            "disallow_incomplete_defs = true\ncheck_untyped_defs = true\n"
        )
        (tmp_path / "pyproject.toml").write_text(toml)
        r = check_pyproject_mypy(tmp_path)
        assert r.passed is True
