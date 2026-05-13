"""Tests for checks.pyproject — pyproject.toml checks."""

from __future__ import annotations

from pathlib import Path

from axm_init.checks.pyproject import (
    check_pyproject_classifiers,
    check_pyproject_coverage,
    check_pyproject_dynamic_version,
    check_pyproject_exists,
    check_pyproject_mypy,
    check_pyproject_pytest,
    check_pyproject_ruff,
    check_pyproject_ruff_rules,
    check_pyproject_urls,
)


class TestCheckPyprojectExists:
    def test_pass(self, gold_project: Path) -> None:
        r = check_pyproject_exists(gold_project)
        assert r.passed is True
        assert r.weight == 4

    def test_fail_missing(self, empty_project: Path) -> None:
        r = check_pyproject_exists(empty_project)
        assert r.passed is False
        assert r.fix != ""

    def test_fail_corrupt(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("{{invalid toml")
        r = check_pyproject_exists(tmp_path)
        assert r.passed is False
        assert "unparsable" in r.message.lower() or "parse" in r.message.lower()


class TestCheckPyprojectUrls:
    def test_pass(self, gold_project: Path) -> None:
        r = check_pyproject_urls(gold_project)
        assert r.passed is True

    def test_fail_missing_section(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
        r = check_pyproject_urls(tmp_path)
        assert r.passed is False

    def test_fail_partial_urls(self, tmp_path: Path) -> None:
        toml = '[project]\nname="x"\n[project.urls]\nHomepage = "h"\nRepository = "r"\n'
        (tmp_path / "pyproject.toml").write_text(toml)
        r = check_pyproject_urls(tmp_path)
        assert r.passed is False
        assert "Documentation" in str(r.details) or "Issues" in str(r.details)


class TestCheckPyprojectDynamicVersion:
    def test_pass(self, gold_project: Path) -> None:
        r = check_pyproject_dynamic_version(gold_project)
        assert r.passed is True

    def test_fail_no_dynamic(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
        r = check_pyproject_dynamic_version(tmp_path)
        assert r.passed is False


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


class TestCheckPyprojectRuff:
    def test_pass(self, gold_project: Path) -> None:
        r = check_pyproject_ruff(gold_project)
        assert r.passed is True

    def test_fail_no_per_file_ignores(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname="x"\n[tool.ruff.lint]\nselect=["E"]\n'
        )
        r = check_pyproject_ruff(tmp_path)
        assert r.passed is False


class TestCheckPyprojectPytest:
    def test_pass(self, gold_project: Path) -> None:
        r = check_pyproject_pytest(gold_project)
        assert r.passed is True

    def test_fail_missing(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text('[project]\nname="x"\n')
        r = check_pyproject_pytest(tmp_path)
        assert r.passed is False


class TestCheckPyprojectCoverage:
    def test_pass(self, gold_project: Path) -> None:
        r = check_pyproject_coverage(gold_project)
        assert r.passed is True

    def test_fail_missing(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text('[project]\nname="x"\n')
        r = check_pyproject_coverage(tmp_path)
        assert r.passed is False


class TestCheckPyprojectClassifiers:
    def test_pass(self, gold_project: Path) -> None:
        r = check_pyproject_classifiers(gold_project)
        assert r.passed is True
        assert r.weight == 1

    def test_fail_no_classifiers(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
        r = check_pyproject_classifiers(tmp_path)
        assert r.passed is False

    def test_fail_missing_typed(self, tmp_path: Path) -> None:
        toml = (
            '[project]\nname="x"\nclassifiers = ['
            '"Development Status :: 3 - Alpha",'
            '"Programming Language :: Python :: 3.12"]\n'
        )
        (tmp_path / "pyproject.toml").write_text(toml)
        r = check_pyproject_classifiers(tmp_path)
        assert r.passed is False
        assert "Typed" in str(r.details)


class TestCheckPyprojectRuffRules:
    def test_pass(self, gold_project: Path) -> None:
        r = check_pyproject_ruff_rules(gold_project)
        assert r.passed is True
        assert r.weight == 2

    def test_fail_no_select(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text('[project]\nname="x"\n')
        r = check_pyproject_ruff_rules(tmp_path)
        assert r.passed is False

    def test_fail_missing_new_rules(self, tmp_path: Path) -> None:
        """Old 5-rule set should now fail — missing S, BLE, PLR, N."""
        toml = (
            '[project]\nname="x"\n[tool.ruff.lint]\n'
            'select = ["E", "F", "I", "UP", "B"]\n'
        )
        (tmp_path / "pyproject.toml").write_text(toml)
        r = check_pyproject_ruff_rules(tmp_path)
        assert r.passed is False
        missing = str(r.details)
        assert "S" in missing
        assert "BLE" in missing
        assert "PLR" in missing
        assert "N" in missing

    def test_pass_with_all(self, tmp_path: Path) -> None:
        """select = ['ALL'] includes everything — should pass."""
        toml = '[project]\nname="x"\n[tool.ruff.lint]\nselect = ["ALL"]\n'
        (tmp_path / "pyproject.toml").write_text(toml)
        r = check_pyproject_ruff_rules(tmp_path)
        assert r.passed is True

    def test_pass_with_extend_select(self, tmp_path: Path) -> None:
        toml = (
            '[project]\nname="x"\n[tool.ruff.lint]\n'
            'select = ["E", "F", "S"]\n'
            'extend-select = ["I", "UP", "B", "BLE", "PLR", "N"]\n'
        )
        (tmp_path / "pyproject.toml").write_text(toml)
        r = check_pyproject_ruff_rules(tmp_path)
        assert r.passed is True

    def test_fail_subset_of_new_rules(self, tmp_path: Path) -> None:
        """Only S and N added — should fail listing BLE, PLR."""
        toml = (
            '[project]\nname="x"\n[tool.ruff.lint]\n'
            'select = ["E", "F", "I", "UP", "B", "S", "N"]\n'
        )
        (tmp_path / "pyproject.toml").write_text(toml)
        r = check_pyproject_ruff_rules(tmp_path)
        assert r.passed is False
        missing = str(r.details)
        assert "BLE" in missing
        assert "PLR" in missing
        # S and N should NOT be in missing
        # (they're in the details string as context, check the sorted list)
        assert r.message == "Missing 2 essential ruff rule(s)"
