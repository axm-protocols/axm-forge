"""Tests for Quality Rules — LintingRule, TypeCheckRule, DiffSizeRule."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


class TestLintingRule:
    """Tests for LintingRule (ruff integration)."""

    def test_clean_project_high_score(self, tmp_path: Path) -> None:
        """Clean project should score 100."""
        from axm_audit.core.rules.quality import LintingRule

        # Create minimal clean Python file
        src = tmp_path / "src"
        src.mkdir()
        (src / "__init__.py").write_text('"""Package init."""\n')
        (src / "main.py").write_text(
            '"""Main module."""\n\n'
            "def hello() -> str:\n"
            '    """Return greeting."""\n'
            '    return "hello"\n'
        )

        rule = LintingRule()
        result = rule.check(tmp_path)
        assert result.details is not None
        assert result.score == 100

    def test_issues_reduce_score(self, tmp_path: Path) -> None:
        """Lint issues should reduce score."""
        from axm_audit.core.rules.quality import LintingRule

        src = tmp_path / "src"
        src.mkdir()
        # Create file with lint issues (unused import)
        (src / "bad.py").write_text("import os\nimport sys\n")

        rule = LintingRule()
        result = rule.check(tmp_path)
        assert result.details is not None
        assert result.score is not None
        assert result.score < 100
        assert result.details["issue_count"] > 0

    def test_lint_details_has_issues_key(self, tmp_path: Path) -> None:
        """details must contain an 'issues' key with a list."""
        from axm_audit.core.rules.quality import LintingRule

        src = tmp_path / "src"
        src.mkdir()
        (src / "__init__.py").write_text('"""Package init."""\n')

        rule = LintingRule()
        result = rule.check(tmp_path)
        assert result.details is not None
        assert "issues" in result.details
        assert isinstance(result.details["issues"], list)

    def test_lint_issues_match_count(self, tmp_path: Path) -> None:
        """len(details['issues']) must equal issue_count (up to cap of 20)."""
        from axm_audit.core.rules.quality import LintingRule

        src = tmp_path / "src"
        src.mkdir()
        (src / "bad.py").write_text("import os\nimport sys\n")

        rule = LintingRule()
        result = rule.check(tmp_path)
        assert result.details is not None
        expected = min(result.details["issue_count"], 20)
        assert len(result.details["issues"]) == expected

    def test_lint_issue_entry_schema(self, tmp_path: Path) -> None:
        """Each issue entry must have file, line, code, message keys."""
        from axm_audit.core.rules.quality import LintingRule

        src = tmp_path / "src"
        src.mkdir()
        (src / "bad.py").write_text("import os\nimport sys\n")

        rule = LintingRule()
        result = rule.check(tmp_path)
        assert result.details is not None
        for entry in result.details["issues"]:
            assert "file" in entry
            assert "line" in entry
            assert "code" in entry
            assert "message" in entry


class TestTypeCheckVenvAlignment:
    """Tests for AXM-796: gate mypy env must match pre-commit hooks."""

    def test_type_check_uses_project_venv(
        self, tmp_path: Path, mocker: MockerFixture
    ) -> None:
        """TypeCheckRule must NOT inject mypy via --with when project has a venv.

        Pre-commit hooks run mypy from the project's own venv, so the gate
        must do the same to see identical type errors and honour the same
        type-stub availability.
        """
        from axm_audit.core.rules.quality import TypeCheckRule

        # Minimal project layout
        src = tmp_path / "src"
        src.mkdir()
        (src / "__init__.py").write_text("")
        (src / "main.py").write_text("def greet(name: str) -> str:\n    return name\n")

        # Simulate a project venv with mypy already installed
        venv_bin = tmp_path / ".venv" / "bin"
        venv_bin.mkdir(parents=True)
        (venv_bin / "python").touch(mode=0o755)

        # Patch run_in_project to capture the call
        mock_run = mocker.patch(
            "axm_audit.core.rules.quality.run_in_project",
            return_value=mocker.MagicMock(stdout="", returncode=0),
        )

        rule = TypeCheckRule()
        rule.check(tmp_path)

        mock_run.assert_called_once()
        _, kwargs = mock_run.call_args
        # Gate must NOT inject mypy — it should use the project's own copy
        with_pkgs = kwargs.get("with_packages") or []
        assert "mypy" not in with_pkgs, (
            "TypeCheckRule must use the project venv's mypy, "
            "not inject via --with; got with_packages={with_pkgs!r}"
        )

    def test_no_unused_ignore_contradiction(
        self, tmp_path: Path, mocker: MockerFixture
    ) -> None:
        """A `# type: ignore` accepted by pre-commit must not become
        an 'unused-ignore' error in the gate.

        When the gate uses the same venv as pre-commit, mypy sees
        identical missing-stub / import errors, so a valid type-ignore
        comment stays valid.  This test verifies the gate passes when
        mypy reports zero errors (i.e. the ignore suppressed a real error).
        """
        from axm_audit.core.rules.quality import TypeCheckRule

        # Minimal project layout
        src = tmp_path / "src"
        src.mkdir()
        (src / "__init__.py").write_text("")
        # File with type: ignore that suppresses a real import error
        (src / "client.py").write_text(
            "import somelib  # type: ignore[import-untyped]\n\n"
            "def call() -> str:\n"
            "    return somelib.run()\n"
        )

        # Simulate project venv
        venv_bin = tmp_path / ".venv" / "bin"
        venv_bin.mkdir(parents=True)
        (venv_bin / "python").touch(mode=0o755)

        # Simulate mypy output: zero errors (type: ignore suppressed the
        # real error, just like pre-commit would see).  If the gate used
        # a different env, mypy might report "unused-ignore" instead.
        mocker.patch(
            "axm_audit.core.rules.quality.run_in_project",
            return_value=mocker.MagicMock(stdout="", returncode=0),
        )

        rule = TypeCheckRule()
        result = rule.check(tmp_path)

        assert result.passed is True
        assert result.details is not None
        assert result.details["error_count"] == 0, (
            "Gate must not produce unused-ignore errors for comments "
            "that pre-commit accepts"
        )


class TestTypeCheckRule:
    """Tests for TypeCheckRule (mypy integration)."""

    def test_typed_project_high_score(self, tmp_path: Path) -> None:
        """Fully typed project should score 100 and pass."""
        from axm_audit.core.rules.quality import TypeCheckRule

        src = tmp_path / "src"
        src.mkdir()
        (src / "__init__.py").write_text("")
        (src / "main.py").write_text(
            'def greet(name: str) -> str:\n    return f"Hello, {name}"\n'
        )

        rule = TypeCheckRule()
        result = rule.check(tmp_path)
        assert result.details is not None
        assert result.passed is True
        assert result.score == 100

    def test_type_errors_reduce_score(self, tmp_path: Path) -> None:
        """Type errors should fail with zero tolerance."""
        from axm_audit.core.rules.quality import TypeCheckRule

        src = tmp_path / "src"
        src.mkdir()
        # Create file with type error
        (src / "bad.py").write_text(
            'def add(a: int, b: int) -> int:\n    return "not an int"\n'
        )

        rule = TypeCheckRule()
        result = rule.check(tmp_path)
        assert result.details is not None
        assert result.details["error_count"] > 0
        assert result.passed is False

    def test_typecheck_includes_tests_dir(self, tmp_path: Path) -> None:
        """TypeCheckRule should include tests/ in checked dirs when present."""
        from axm_audit.core.rules.quality import TypeCheckRule

        src = tmp_path / "src"
        src.mkdir()
        (src / "__init__.py").write_text("")
        (src / "main.py").write_text(
            'def greet(name: str) -> str:\n    return f"Hello, {name}"\n'
        )
        tests = tmp_path / "tests"
        tests.mkdir()
        (tests / "__init__.py").write_text("")
        (tests / "test_main.py").write_text(
            "def test_greet() -> None:\n    assert True\n"
        )

        rule = TypeCheckRule()
        result = rule.check(tmp_path)
        assert result.details is not None
        assert "tests/" in result.details.get("checked", "")

    def test_typecheck_no_tests_dir(self, tmp_path: Path) -> None:
        """TypeCheckRule should work fine without tests/ directory."""
        from axm_audit.core.rules.quality import TypeCheckRule

        src = tmp_path / "src"
        src.mkdir()
        (src / "__init__.py").write_text("")
        (src / "main.py").write_text(
            'def greet(name: str) -> str:\n    return f"Hello, {name}"\n'
        )
        # No tests/ directory

        rule = TypeCheckRule()
        result = rule.check(tmp_path)
        assert result.details is not None
        assert result.details.get("checked") == "src/"

    def test_typecheck_details_has_errors_key(self, tmp_path: Path) -> None:
        """details must contain an 'errors' key with a list."""
        from axm_audit.core.rules.quality import TypeCheckRule

        src = tmp_path / "src"
        src.mkdir()
        (src / "__init__.py").write_text("")
        (src / "main.py").write_text(
            'def greet(name: str) -> str:\n    return f"Hello, {name}"\n'
        )

        rule = TypeCheckRule()
        result = rule.check(tmp_path)
        assert result.details is not None
        assert "errors" in result.details
        assert isinstance(result.details["errors"], list)

    def test_typecheck_errors_match_count(self, tmp_path: Path) -> None:
        """len(details['errors']) must equal error_count."""
        from axm_audit.core.rules.quality import TypeCheckRule

        src = tmp_path / "src"
        src.mkdir()
        (src / "bad.py").write_text(
            'def add(a: int, b: int) -> int:\n    return "not an int"\n'
        )

        rule = TypeCheckRule()
        result = rule.check(tmp_path)
        assert result.details is not None
        assert len(result.details["errors"]) == result.details["error_count"]

    def test_typecheck_error_entry_schema(self, tmp_path: Path) -> None:
        """Each error entry must have file, line, message, code keys."""
        from axm_audit.core.rules.quality import TypeCheckRule

        src = tmp_path / "src"
        src.mkdir()
        (src / "bad.py").write_text(
            'def add(a: int, b: int) -> int:\n    return "not an int"\n'
        )

        rule = TypeCheckRule()
        result = rule.check(tmp_path)
        assert result.details is not None
        for entry in result.details["errors"]:
            assert "file" in entry
            assert "line" in entry
            assert "message" in entry
            assert "code" in entry

    def test_typecheck_no_errors_empty_list(self, tmp_path: Path) -> None:
        """When no errors, details['errors'] should be []."""
        from axm_audit.core.rules.quality import TypeCheckRule

        src = tmp_path / "src"
        src.mkdir()
        (src / "__init__.py").write_text("")
        (src / "main.py").write_text(
            'def greet(name: str) -> str:\n    return f"Hello, {name}"\n'
        )

        rule = TypeCheckRule()
        result = rule.check(tmp_path)
        assert result.details is not None
        assert result.details["errors"] == []

    def test_type_check_zero_errors_passes(self, tmp_path: Path) -> None:
        """Zero mypy errors → passed=True, score=100."""
        from axm_audit.core.rules.quality import TypeCheckRule

        src = tmp_path / "src"
        src.mkdir()
        (src / "__init__.py").write_text("")
        (src / "clean.py").write_text("def double(x: int) -> int:\n    return x * 2\n")

        rule = TypeCheckRule()
        result = rule.check(tmp_path)
        assert result.passed is True
        assert result.details is not None
        assert result.score == 100

    def test_type_check_one_error_fails(self, tmp_path: Path) -> None:
        """One mypy error → passed=False (zero tolerance)."""
        from axm_audit.core.rules.quality import TypeCheckRule

        src = tmp_path / "src"
        src.mkdir()
        (src / "bad.py").write_text(
            'def add(a: int, b: int) -> int:\n    return "wrong"\n'
        )

        rule = TypeCheckRule()
        result = rule.check(tmp_path)
        assert result.passed is False
        assert result.details is not None
        assert result.details["error_count"] == 1

    def test_type_check_two_errors_fails(self, tmp_path: Path) -> None:
        """Two mypy errors → passed=False (zero tolerance)."""
        from axm_audit.core.rules.quality import TypeCheckRule

        src = tmp_path / "src"
        src.mkdir()
        (src / "bad.py").write_text(
            'def add(a: int, b: int) -> int:\n    return "wrong"\n\n'
            'def sub(a: int, b: int) -> int:\n    return "also wrong"\n'
        )

        rule = TypeCheckRule()
        result = rule.check(tmp_path)
        assert result.passed is False
        assert result.details is not None
        assert result.details["error_count"] == 2

    def test_lint_threshold_unchanged(self, tmp_path: Path) -> None:
        """Lint rule still uses score threshold — no regression from type fix."""
        from axm_audit.core.rules.quality import LintingRule

        src = tmp_path / "src"
        src.mkdir()
        (src / "__init__.py").write_text('"""Package."""\n')
        # Single unused import → small score reduction, still above threshold
        (src / "mild.py").write_text('"""Mild issue."""\nimport os\n')

        rule = LintingRule()
        result = rule.check(tmp_path)
        assert result.details is not None
        # Lint uses scoring threshold, not zero-tolerance
        assert result.details["issue_count"] > 0
        assert result.score is not None
        assert result.score >= 90


class TestDiffSizeRule:
    """Integration tests for DiffSizeRule config reading (real pyproject.toml I/O)."""

    def test_config_override_ideal(self, tmp_path: Path) -> None:
        """pyproject.toml with diff_size_ideal=300 → rule uses 300."""
        from axm_audit.core.rules.quality import read_diff_config

        (tmp_path / "pyproject.toml").write_text(
            "[tool.axm-audit]\ndiff_size_ideal = 300\n"
        )
        ideal, max_lines = read_diff_config(tmp_path)
        assert ideal == 300
        assert max_lines == 1200  # default

    def test_config_override_max(self, tmp_path: Path) -> None:
        """pyproject.toml with diff_size_max=1000 → rule uses 1000."""
        from axm_audit.core.rules.quality import read_diff_config

        (tmp_path / "pyproject.toml").write_text(
            "[tool.axm-audit]\ndiff_size_max = 1000\n"
        )
        ideal, max_lines = read_diff_config(tmp_path)
        assert ideal == 400  # default
        assert max_lines == 1000

    def test_no_config_uses_defaults(self, tmp_path: Path) -> None:
        """pyproject.toml without [tool.axm-audit] → defaults."""
        from axm_audit.core.rules.quality import read_diff_config

        (tmp_path / "pyproject.toml").write_text('[project]\nname = "demo"\n')
        ideal, max_lines = read_diff_config(tmp_path)
        assert ideal == 400
        assert max_lines == 1200

    def test_partial_config(self, tmp_path: Path) -> None:
        """Only diff_size_ideal set → diff_size_max uses default."""
        from axm_audit.core.rules.quality import read_diff_config

        (tmp_path / "pyproject.toml").write_text(
            "[tool.axm-audit]\ndiff_size_ideal = 250\n"
        )
        ideal, max_lines = read_diff_config(tmp_path)
        assert ideal == 250
        assert max_lines == 1200

    def test_invalid_config_value(self, tmp_path: Path) -> None:
        """Non-numeric diff_size_ideal → falls back to default."""
        from axm_audit.core.rules.quality import read_diff_config

        (tmp_path / "pyproject.toml").write_text(
            '[tool.axm-audit]\ndiff_size_ideal = "abc"\n'
        )
        ideal, max_lines = read_diff_config(tmp_path)
        assert ideal == 400
        assert max_lines == 1200

    def test_negative_threshold(self, tmp_path: Path) -> None:
        """Negative diff_size_ideal → falls back to default."""
        from axm_audit.core.rules.quality import read_diff_config

        (tmp_path / "pyproject.toml").write_text(
            "[tool.axm-audit]\ndiff_size_ideal = -10\n"
        )
        ideal, max_lines = read_diff_config(tmp_path)
        assert ideal == 400
        assert max_lines == 1200

    def test_missing_pyproject(self, tmp_path: Path) -> None:
        """No pyproject.toml at all → defaults apply."""
        from axm_audit.core.rules.quality import read_diff_config

        ideal, max_lines = read_diff_config(tmp_path)
        assert ideal == 400
        assert max_lines == 1200
