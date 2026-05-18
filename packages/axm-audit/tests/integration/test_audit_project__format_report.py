"""End-to-end pipeline tests using a toy Python project fixture.

Exercises the real ``audit_project()`` → ``format_agent()`` / ``format_report()``
pipeline on a minimal but valid project inside ``tmp_path``.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from axm_audit.core.auditor import audit_project
from axm_audit.formatters import format_report

if TYPE_CHECKING:
    pass


# ── Unit tests ───────────────────────────────────────────────────────


class TestToyProjectFixture:
    """Tests for the toy project fixture itself."""

    def test_toy_project_fixture_creates_structure(self, toy_project: Path) -> None:
        """Fixture creates expected directory structure."""
        assert (toy_project / "pyproject.toml").is_file()
        assert (toy_project / "src" / "toy" / "__init__.py").is_file()
        assert (toy_project / "src" / "toy" / "core.py").is_file()
        assert (toy_project / "tests" / "test_core.py").is_file()


def test_format_report_readable(toy_project: Path) -> None:
    """format_report output contains banner and score."""
    result = audit_project(toy_project)
    report = format_report(result)

    assert isinstance(report, str)
    assert "axm-audit" in report
    assert "Score:" in report
