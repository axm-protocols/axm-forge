"""Integration tests for ``format_agent_text`` over a hand-built ``ProjectResult``.

Extracted from ``test_format_agent__format_agent_text.py`` (file split by
covered symbol tuple).
"""

from pathlib import Path

import pytest

from axm_init.models.check import CheckResult, ProjectResult

pytestmark = pytest.mark.integration


class TestFormatAgentTextProjectResult:
    """format_agent_text preserves multi-line content from a ProjectResult."""

    def test_multiline_fix_is_kept_verbatim(self, tmp_path: Path) -> None:
        """A multi-line fix body must survive intact, line by line."""
        from axm_init.core.checker import format_agent_text

        checks = [
            CheckResult(
                name="pyproject.demo",
                category="pyproject",
                passed=False,
                weight=5,
                message="incomplete",
                details=["Missing: alpha", "Present: beta"],
                fix="First line.\nSecond line.\nThird line.",
            ),
        ]
        result = ProjectResult.from_checks(tmp_path, checks)
        text = format_agent_text(result)
        assert "First line." in text
        assert "Second line." in text
        assert "Third line." in text
        assert "Missing: alpha" in text
        assert "Present: beta" in text

    def test_not_applicable_renders_na_not_false_failure(self, tmp_path: Path) -> None:
        """A not-applicable run renders N/A, never a 0/100 Grade F header.

        When no weighted check ran (every check ``weight == 0``), the run is
        not applicable: the LLM-facing header must show ``N/A`` in place of
        the ``{grade} {score}/100`` couple — otherwise the agent reads a real
        failure where a dimension simply does not apply. If the guard is
        replaced by ``pass`` the verdict falls back to ``F 0/100`` and the
        ``"0/100"`` assertion below flips.
        """
        from axm_init.core.checker import format_agent_text

        checks = [
            CheckResult(
                name="workspace.only_root",
                category="workspace",
                passed=True,
                weight=0,
                message="Not applicable in this context",
                details=[],
                fix="",
            ),
        ]
        result = ProjectResult.from_checks(tmp_path, checks)
        assert result.not_applicable
        text = format_agent_text(result)
        assert "N/A" in text
        assert "0/100" not in text
        assert "F 0/100" not in text

    def test_applicable_still_renders_grade_score(self, tmp_path: Path) -> None:
        """Non-regression: an applicable run keeps ``{grade} {score}/100``."""
        from axm_init.core.checker import format_agent_text

        checks = [
            CheckResult(
                name="pyproject.demo",
                category="pyproject",
                passed=True,
                weight=10,
                message="ok",
                details=[],
                fix="",
            ),
        ]
        result = ProjectResult.from_checks(tmp_path, checks)
        assert result.applicable
        text = format_agent_text(result)
        assert f"{result.grade.value} {result.score}/100" in text
        assert "100/100" in text
