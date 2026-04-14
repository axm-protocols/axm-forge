"""Tests for PyprojectCompletenessRule."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.core.rules.structure import (
    PyprojectCompletenessRule,
    _check_fields,
)


@pytest.fixture
def rule() -> PyprojectCompletenessRule:
    return PyprojectCompletenessRule()


def _write_pyproject(tmp_path: Path, content: str) -> Path:
    (tmp_path / "pyproject.toml").write_text(content)
    return tmp_path


class TestPyprojectCompletenessRule:
    """Tests for PyprojectCompletenessRule (PEP 621 validation)."""

    def test_complete_pyproject_passes(self, tmp_path: Path) -> None:
        """All 9 fields present → score=100, passed=True."""
        from axm_audit.core.rules.structure import PyprojectCompletenessRule

        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            "[project]\n"
            'name = "my-pkg"\n'
            'version = "1.0.0"\n'
            'description = "A package"\n'
            'requires-python = ">=3.12"\n'
            'license = "MIT"\n'
            'readme = "README.md"\n'
            'authors = [{name = "Test"}]\n'
            'classifiers = ["Development Status :: 3"]\n'
            "\n"
            "[project.urls]\n"
            'Homepage = "https://example.com"\n'
        )

        rule = PyprojectCompletenessRule()
        result = rule.check(tmp_path)

        assert result.passed is True
        assert result.details is not None
        assert result.details["score"] == 100

    def test_minimal_pyproject_fails(self, tmp_path: Path) -> None:
        """Only name → low score, passed=False."""
        from axm_audit.core.rules.structure import PyprojectCompletenessRule

        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "my-pkg"\n')

        rule = PyprojectCompletenessRule()
        result = rule.check(tmp_path)

        assert result.passed is False
        assert result.details is not None
        assert result.details["score"] < 50

    def test_dynamic_version_counts(self, tmp_path: Path) -> None:
        """dynamic = ['version'] should count as version present."""
        from axm_audit.core.rules.structure import PyprojectCompletenessRule

        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            "[project]\n"
            'name = "my-pkg"\n'
            'dynamic = ["version"]\n'
            'description = "A package"\n'
            'requires-python = ">=3.12"\n'
            'license = "MIT"\n'
            'readme = "README.md"\n'
            'authors = [{name = "Test"}]\n'
            'classifiers = ["Development Status :: 3"]\n'
            "\n"
            "[project.urls]\n"
            'Homepage = "https://example.com"\n'
        )

        rule = PyprojectCompletenessRule()
        result = rule.check(tmp_path)

        assert result.passed is True
        assert result.details is not None
        assert result.details["score"] == 100

    def test_missing_pyproject_fails(self, tmp_path: Path) -> None:
        """No pyproject.toml → score=0, passed=False."""
        from axm_audit.core.rules.structure import PyprojectCompletenessRule

        rule = PyprojectCompletenessRule()
        result = rule.check(tmp_path)

        assert result.passed is False
        assert result.details is not None
        assert result.details["score"] == 0

    def test_rule_id(self) -> None:
        """Rule ID should be STRUCTURE_PYPROJECT."""
        from axm_audit.core.rules.structure import PyprojectCompletenessRule

        assert PyprojectCompletenessRule().rule_id == "STRUCTURE_PYPROJECT"

    def test_malformed_toml(self, tmp_path: Path) -> None:
        """Malformed pyproject.toml → parse error result."""
        from axm_audit.core.rules.structure import PyprojectCompletenessRule

        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project\nbroken syntax")

        rule = PyprojectCompletenessRule()
        result = rule.check(tmp_path)

        assert result.passed is False
        assert "parse error" in result.message
        assert result.details is not None
        assert result.details["score"] == 0


# ---------------------------------------------------------------------------
# Unit tests — missing key + text field
# ---------------------------------------------------------------------------


class TestMissingAndText:
    """Tests for details['missing'] and text field on CheckResult."""

    def test_complete_pyproject_no_missing(
        self, rule: PyprojectCompletenessRule, tmp_path: Path
    ) -> None:
        """All 9 fields present → missing==[], text is None."""
        content = (
            "[project]\n"
            'name = "pkg"\n'
            'description = "A package"\n'
            'requires-python = ">=3.12"\n'
            'license = "MIT"\n'
            'authors = [{name = "A"}]\n'
            'version = "1.0.0"\n'
            'classifiers = ["Development Status :: 3 - Alpha"]\n'
            'readme = "README.md"\n'
            "\n"
            "[project.urls]\n"
            'Homepage = "https://example.com"\n'
        )
        proj = _write_pyproject(tmp_path, content)
        result = rule.check(proj)

        assert result.details is not None
        assert result.details["missing"] == []
        assert result.text is None

    def test_partial_pyproject_missing_fields(
        self, rule: PyprojectCompletenessRule, tmp_path: Path
    ) -> None:
        """7/9 fields (no classifiers, readme) → missing list + text."""
        content = (
            "[project]\n"
            'name = "pkg"\n'
            'description = "A package"\n'
            'requires-python = ">=3.12"\n'
            'license = "MIT"\n'
            'authors = [{name = "A"}]\n'
            'version = "1.0.0"\n'
            "\n"
            "[project.urls]\n"
            'Homepage = "https://example.com"\n'
        )
        proj = _write_pyproject(tmp_path, content)
        result = rule.check(proj)

        assert result.details is not None
        assert result.details["missing"] == ["classifiers", "readme"]
        assert result.text == "\u2022 missing: classifiers, readme"

    def test_minimal_pyproject_missing_list(
        self, rule: PyprojectCompletenessRule, tmp_path: Path
    ) -> None:
        """Only name → 8 missing, text starts with bullet."""
        proj = _write_pyproject(tmp_path, '[project]\nname = "pkg"\n')
        result = rule.check(proj)

        assert result.details is not None
        assert len(result.details["missing"]) == 8
        assert result.text is not None
        assert result.text.startswith("\u2022 missing:")

    def test_missing_file_no_text(
        self, rule: PyprojectCompletenessRule, tmp_path: Path
    ) -> None:
        """No pyproject.toml → text is None (error path)."""
        result = rule.check(tmp_path)
        assert result.text is None

    def test_malformed_toml_no_text(
        self, rule: PyprojectCompletenessRule, tmp_path: Path
    ) -> None:
        """Broken TOML → text is None (error path)."""
        (tmp_path / "pyproject.toml").write_text("[project\ninvalid")
        result = rule.check(tmp_path)
        assert result.text is None


# ---------------------------------------------------------------------------
# Functional tests — _check_fields
# ---------------------------------------------------------------------------


class TestCheckFields:
    """Tests for the _check_fields helper."""

    def test_check_fields_returns_tuple(self) -> None:
        """_check_fields({\"name\": \"x\"}) returns (1, [8 missing])."""
        present, missing = _check_fields({"name": "x"})
        assert present == 1
        assert "description" in missing
        assert "requires-python" in missing
        assert "license" in missing
        assert "authors" in missing
        assert "version" in missing
        assert "urls" in missing
        assert "classifiers" in missing
        assert "readme" in missing

    def test_check_fields_dynamic_version(self) -> None:
        """dynamic=[\"version\"] → version not in missing."""
        _present, missing = _check_fields({"name": "x", "dynamic": ["version"]})
        assert "version" not in missing


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge-case scenarios for _check_fields."""

    def test_empty_project_table(self) -> None:
        """Empty project table → 0 present, 9 missing."""
        present, missing = _check_fields({})
        assert present == 0
        assert len(missing) == 9

    def test_dynamic_version_only(self) -> None:
        """dynamic=[\"version\"] but no static version → version present."""
        present, missing = _check_fields({"dynamic": ["version"]})
        assert "version" not in missing
        assert present == 1

    def test_urls_present_but_empty(self) -> None:
        """Empty urls dict is falsy → urls counted as missing."""
        _present, missing = _check_fields({"name": "x", "urls": {}})
        assert "urls" in missing
