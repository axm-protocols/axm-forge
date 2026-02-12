"""Tests for PyprojectCompletenessRule."""

from pathlib import Path


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
