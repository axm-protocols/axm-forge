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
