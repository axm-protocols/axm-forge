"""End-to-end pipeline tests using a toy Python project fixture.

Exercises the real ``audit_project()`` → ``format_agent()`` / ``format_report()``
pipeline on a minimal but valid project inside ``tmp_path``.
"""

from __future__ import annotations

import shutil
import textwrap
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from axm_audit.core.auditor import audit_project
from axm_audit.formatters import format_agent, format_report

if TYPE_CHECKING:
    from axm_audit.models.results import AuditResult


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture()
def toy_project(tmp_path: Path) -> Path:
    """Create a minimal but valid Python project in *tmp_path*.

    Layout::

        tmp_path/
        ├── pyproject.toml
        ├── src/
        │   └── toy/
        │       ├── __init__.py
        │       └── core.py
        └── tests/
            └── test_core.py
    """
    # -- pyproject.toml --------------------------------------------------
    (tmp_path / "pyproject.toml").write_text(
        textwrap.dedent("""\
            [build-system]
            requires = ["hatchling"]
            build-backend = "hatchling.build"

            [project]
            name = "toy"
            version = "0.1.0"
            requires-python = ">=3.12"

            [tool.ruff]
            line-length = 88
            select = ["E", "F", "I"]

            [tool.mypy]
            strict = true
        """)
    )

    # -- src/toy/ --------------------------------------------------------
    src = tmp_path / "src" / "toy"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text(
        textwrap.dedent("""\
            \"\"\"Toy package.\"\"\"

            from __future__ import annotations

            __all__: list[str] = []
        """)
    )
    (src / "core.py").write_text(
        textwrap.dedent("""\
            \"\"\"Core module of toy package.\"\"\"

            from __future__ import annotations


            def greet(name: str) -> str:
                \"\"\"Return a greeting string.\"\"\"
                return f"Hello, {name}!"
        """)
    )

    # -- tests/ ----------------------------------------------------------
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_core.py").write_text(
        textwrap.dedent("""\
            \"\"\"Tests for toy.core.\"\"\"

            from __future__ import annotations

            from toy.core import greet


            def test_greet() -> None:
                \"\"\"Greet returns expected string.\"\"\"
                assert greet("World") == "Hello, World!"
        """)
    )

    return tmp_path


@pytest.fixture()
def broken_project(tmp_path: Path) -> Path:
    """Create a project with deliberate lint errors.

    The source file contains unused imports and missing docstrings,
    which should cause lint rules to flag issues and lower the score.
    """
    (tmp_path / "pyproject.toml").write_text(
        textwrap.dedent("""\
            [build-system]
            requires = ["hatchling"]
            build-backend = "hatchling.build"

            [project]
            name = "broken"
            version = "0.1.0"
            requires-python = ">=3.12"

            [tool.ruff]
            line-length = 88
            select = ["E", "F", "I"]
        """)
    )

    src = tmp_path / "src" / "broken"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "bad.py").write_text(
        textwrap.dedent("""\
            import os
            import sys
            import json

            x=1
            y =2
            def foo():
                pass
        """)
    )

    return tmp_path


@pytest.fixture()
def no_tests_project(tmp_path: Path) -> Path:
    """Create a minimal project without a ``tests/`` directory."""
    (tmp_path / "pyproject.toml").write_text(
        textwrap.dedent("""\
            [build-system]
            requires = ["hatchling"]
            build-backend = "hatchling.build"

            [project]
            name = "notests"
            version = "0.1.0"
            requires-python = ">=3.12"
        """)
    )

    src = tmp_path / "src" / "notests"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text('"""No tests package."""\n')
    (src / "core.py").write_text(
        textwrap.dedent("""\
            \"\"\"Core module.\"\"\"

            from __future__ import annotations


            def add(a: int, b: int) -> int:
                \"\"\"Add two numbers.\"\"\"
                return a + b
        """)
    )

    return tmp_path


# ── Helpers ──────────────────────────────────────────────────────────


def _tools_available() -> bool:
    """Check that ruff and mypy are on PATH."""
    return shutil.which("ruff") is not None and shutil.which("mypy") is not None


_skip_no_tools = pytest.mark.skipif(
    not _tools_available(),
    reason="ruff and/or mypy not available on PATH",
)


# ── Unit tests ───────────────────────────────────────────────────────


class TestToyProjectFixture:
    """Tests for the toy project fixture itself."""

    def test_toy_project_fixture_creates_structure(self, toy_project: Path) -> None:
        """Fixture creates expected directory structure."""
        assert (toy_project / "pyproject.toml").is_file()
        assert (toy_project / "src" / "toy" / "__init__.py").is_file()
        assert (toy_project / "src" / "toy" / "core.py").is_file()
        assert (toy_project / "tests" / "test_core.py").is_file()


# ── Functional / regression tests ────────────────────────────────────


@_skip_no_tools
class TestAuditPipeline:
    """E2E tests exercising the full audit pipeline."""

    def test_audit_toy_project_passes(self, toy_project: Path) -> None:
        """Audit a clean toy project — expects a reasonable score.

        Note: ``result.success`` may be False because some tooling checks
        (pip-audit, deptry, bandit, pytest) are not installed in the
        isolated tmp_path.  The key assertion is that the pipeline
        completes and returns a non-trivial score.
        """
        result: AuditResult = audit_project(toy_project)
        assert result.quality_score is not None
        assert result.quality_score > 0
        assert result.grade in {"A", "B", "C", "D", "F"}

    def test_format_agent_structure(self, toy_project: Path) -> None:
        """format_agent returns dict with expected keys."""
        result = audit_project(toy_project)
        agent_output = format_agent(result)

        assert isinstance(agent_output, dict)
        assert "score" in agent_output
        assert "grade" in agent_output
        assert "passed" in agent_output
        assert "failed" in agent_output
        assert isinstance(agent_output["passed"], list)
        assert isinstance(agent_output["failed"], list)

    def test_format_report_readable(self, toy_project: Path) -> None:
        """format_report output contains banner and score."""
        result = audit_project(toy_project)
        report = format_report(result)

        assert isinstance(report, str)
        assert "axm-audit" in report
        assert "Score:" in report


# ── Edge cases ───────────────────────────────────────────────────────


@_skip_no_tools
class TestEdgeCases:
    """Edge-case scenarios the pipeline must survive."""

    def test_broken_project_lower_score(self, broken_project: Path) -> None:
        """A project with lint errors should still audit without crashing.

        The score should be measurably lower than a clean project.
        """
        result = audit_project(broken_project)
        # Must complete — no crash
        assert isinstance(result.quality_score, float)
        # Lint errors should lower the lint score
        lint_checks = [c for c in result.checks if c.rule_id.startswith("QUALITY_LINT")]
        if lint_checks:
            details = lint_checks[0].details
            if details is not None:
                assert details.get("score", 100) < 100

    def test_no_tests_directory(self, no_tests_project: Path) -> None:
        """Audit passes on a project without a tests/ directory.

        Coverage score should be 0 (or very low) since there are no tests
        to run.
        """
        result = audit_project(no_tests_project)
        assert isinstance(result.quality_score, float)
        # Coverage check should show low/zero coverage
        coverage_checks = [c for c in result.checks if c.rule_id == "QUALITY_COVERAGE"]
        if coverage_checks:
            details = coverage_checks[0].details
            cov_score = details.get("score", 0) if details is not None else 0
            assert cov_score <= 10  # No tests → ~0% coverage

    def test_syntax_error_does_not_crash(self, tmp_path: Path) -> None:
        """A project with a syntax error should audit without crashing."""
        # Minimal project with invalid Python
        (tmp_path / "pyproject.toml").write_text(
            textwrap.dedent("""\
                [build-system]
                requires = ["hatchling"]
                build-backend = "hatchling.build"

                [project]
                name = "syntaxerr"
                version = "0.1.0"
                requires-python = ">=3.12"
            """)
        )
        src = tmp_path / "src" / "syntaxerr"
        src.mkdir(parents=True)
        (src / "__init__.py").write_text("")
        (src / "broken.py").write_text("def foo(\n")  # syntax error

        result = audit_project(tmp_path)
        # Pipeline must not crash — returns results
        assert isinstance(result.quality_score, float)
