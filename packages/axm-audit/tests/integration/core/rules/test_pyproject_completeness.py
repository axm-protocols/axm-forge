"""Tests for PyprojectCompletenessRule."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.core.rules.structure import (
    PyprojectCompletenessRule,
)


@pytest.fixture
def rule() -> PyprojectCompletenessRule:
    return PyprojectCompletenessRule()


def _write_pyproject(tmp_path: Path, content: str) -> Path:
    (tmp_path / "pyproject.toml").write_text(content)
    return tmp_path


class TestPyprojectCompletenessRuleIO:
    """Tests for PyprojectCompletenessRule (PEP 621 validation) — filesystem I/O."""

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
        assert result.score == 100

    def test_minimal_pyproject_fails(self, tmp_path: Path) -> None:
        """Only name → low score, passed=False."""
        from axm_audit.core.rules.structure import PyprojectCompletenessRule

        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "my-pkg"\n')

        rule = PyprojectCompletenessRule()
        result = rule.check(tmp_path)

        assert result.passed is False
        assert result.details is not None
        assert result.score is not None
        assert result.score < 50

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
        assert result.score == 100

    def test_missing_pyproject_fails(self, tmp_path: Path) -> None:
        """No pyproject.toml → score=0, passed=False."""
        from axm_audit.core.rules.structure import PyprojectCompletenessRule

        rule = PyprojectCompletenessRule()
        result = rule.check(tmp_path)

        assert result.passed is False
        assert result.details is not None
        assert result.score == 0

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
        assert result.score == 0


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
