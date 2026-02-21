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


class TestFileExistsRule:
    """Tests for FileExistsRule."""

    def test_file_exists(self, tmp_path: Path) -> None:
        """Existing file passes."""
        from axm_audit.core.rules.structure import FileExistsRule

        (tmp_path / "README.md").write_text("# Hello")

        rule = FileExistsRule(file_name="README.md")
        result = rule.check(tmp_path)

        assert result.passed is True
        assert "exists" in result.message

    def test_file_missing(self, tmp_path: Path) -> None:
        """Missing file fails."""
        from axm_audit.core.rules.structure import FileExistsRule

        rule = FileExistsRule(file_name="README.md")
        result = rule.check(tmp_path)

        assert result.passed is False
        assert "not found" in result.message

    def test_rule_id_includes_filename(self) -> None:
        """Rule ID should include the filename."""
        from axm_audit.core.rules.structure import FileExistsRule

        rule = FileExistsRule(file_name="README.md")
        assert rule.rule_id == "FILE_EXISTS_README.md"


class TestDirectoryExistsRule:
    """Tests for DirectoryExistsRule."""

    def test_directory_exists(self, tmp_path: Path) -> None:
        """Existing directory passes."""
        from axm_audit.core.rules.structure import DirectoryExistsRule

        (tmp_path / "src").mkdir()

        rule = DirectoryExistsRule(dir_name="src")
        result = rule.check(tmp_path)

        assert result.passed is True
        assert "exists" in result.message

    def test_directory_missing(self, tmp_path: Path) -> None:
        """Missing directory fails."""
        from axm_audit.core.rules.structure import DirectoryExistsRule

        rule = DirectoryExistsRule(dir_name="src")
        result = rule.check(tmp_path)

        assert result.passed is False
        assert "not found" in result.message

    def test_rule_id_includes_dirname(self) -> None:
        """Rule ID should include the dir name."""
        from axm_audit.core.rules.structure import DirectoryExistsRule

        rule = DirectoryExistsRule(dir_name="tests")
        assert rule.rule_id == "DIR_EXISTS_tests"
