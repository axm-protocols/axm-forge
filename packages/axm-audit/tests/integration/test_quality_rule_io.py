"""Tests for Quality Rules — LintingRule, TypeCheckRule, DiffSizeRule."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

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

    @pytest.mark.parametrize(
        ("rule_cls", "source", "collection_key"),
        [
            pytest.param(
                "LintingRule",
                "import os\nimport sys\n",
                "issues",
                id="lint_issue_entry_schema",
            ),
        ],
    )
    def test_issue_entry_schema(
        self, tmp_path: Path, rule_cls: str, source: str, collection_key: str
    ) -> None:
        """Each issue/error entry must have file, line, code, message keys."""
        from axm_audit.core.rules import quality as q

        src = tmp_path / "src"
        src.mkdir()
        (src / "bad.py").write_text(source)

        rule = getattr(q, rule_cls)()
        result = rule.check(tmp_path)
        assert result.details is not None
        for entry in result.details[collection_key]:
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

    @pytest.mark.parametrize(
        ("filename", "source"),
        [
            pytest.param(
                "main.py",
                'def greet(name: str) -> str:\n    return f"Hello, {name}"\n',
                id="typed_greet",
            ),
            pytest.param(
                "clean.py",
                "def double(x: int) -> int:\n    return x * 2\n",
                id="typed_double",
            ),
        ],
    )
    def test_typed_project_high_score(
        self, tmp_path: Path, filename: str, source: str
    ) -> None:
        """Fully typed project (zero mypy errors) → passed=True, score=100."""
        from axm_audit.core.rules.quality import TypeCheckRule

        src = tmp_path / "src"
        src.mkdir()
        (src / "__init__.py").write_text("")
        (src / filename).write_text(source)

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

    @pytest.mark.parametrize(
        ("rule_cls", "source", "collection_key"),
        [
            pytest.param(
                "TypeCheckRule",
                'def add(a: int, b: int) -> int:\n    return "not an int"\n',
                "errors",
                id="typecheck_error_entry_schema",
            ),
        ],
    )
    def test_error_entry_schema(
        self, tmp_path: Path, rule_cls: str, source: str, collection_key: str
    ) -> None:
        """Each error entry must have file, line, message, code keys."""
        from axm_audit.core.rules import quality as q

        src = tmp_path / "src"
        src.mkdir()
        (src / "bad.py").write_text(source)

        rule = getattr(q, rule_cls)()
        result = rule.check(tmp_path)
        assert result.details is not None
        for entry in result.details[collection_key]:
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

    @pytest.mark.parametrize(
        ("source", "expected_error_count"),
        [
            pytest.param(
                'def add(a: int, b: int) -> int:\n    return "wrong"\n',
                1,
                id="one_error",
            ),
            pytest.param(
                'def add(a: int, b: int) -> int:\n    return "wrong"\n\n'
                'def sub(a: int, b: int) -> int:\n    return "also wrong"\n',
                2,
                id="two_errors",
            ),
        ],
    )
    def test_type_check_n_errors_fails(
        self, tmp_path: Path, source: str, expected_error_count: int
    ) -> None:
        """N mypy errors → passed=False (zero tolerance)."""
        from axm_audit.core.rules.quality import TypeCheckRule

        src = tmp_path / "src"
        src.mkdir()
        (src / "bad.py").write_text(source)

        rule = TypeCheckRule()
        result = rule.check(tmp_path)
        assert result.passed is False
        assert result.details is not None
        assert result.details["error_count"] == expected_error_count

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

    @pytest.mark.parametrize(
        ("pyproject_content", "expected_ideal", "expected_max"),
        [
            pytest.param(
                "[tool.axm-audit]\ndiff_size_ideal = 300\n",
                300,
                1200,
                id="override_ideal",
            ),
            pytest.param(
                "[tool.axm-audit]\ndiff_size_max = 1000\n",
                400,
                1000,
                id="override_max",
            ),
            pytest.param(
                '[project]\nname = "demo"\n',
                400,
                1200,
                id="no_axm_audit_section_uses_defaults",
            ),
            pytest.param(
                "[tool.axm-audit]\ndiff_size_ideal = 250\n",
                250,
                1200,
                id="partial_config_ideal_only",
            ),
            pytest.param(
                '[tool.axm-audit]\ndiff_size_ideal = "abc"\n',
                400,
                1200,
                id="invalid_non_numeric_falls_back",
            ),
            pytest.param(
                "[tool.axm-audit]\ndiff_size_ideal = -10\n",
                400,
                1200,
                id="negative_threshold_falls_back",
            ),
            pytest.param(None, 400, 1200, id="missing_pyproject_uses_defaults"),
        ],
    )
    def test_read_diff_config(
        self,
        tmp_path: Path,
        pyproject_content: str | None,
        expected_ideal: int,
        expected_max: int,
    ) -> None:
        """read_diff_config honours config overrides and falls back to defaults."""
        from axm_audit.core.rules.quality import read_diff_config

        if pyproject_content is not None:
            (tmp_path / "pyproject.toml").write_text(pyproject_content)
        ideal, max_lines = read_diff_config(tmp_path)
        assert ideal == expected_ideal
        assert max_lines == expected_max
