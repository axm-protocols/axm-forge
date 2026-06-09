"""Integration tests for ``format_agent_text`` — compact text rendering.

Extracted from ``test_format_agent__format_agent_text.py`` (file split by
covered symbol tuple).
"""

from pathlib import Path

import pytest

from tests.integration._helpers import _make_result

pytestmark = pytest.mark.integration


class TestFormatAgentText:
    """Tests for format_agent_text() — compact text rendering for the LLM."""

    def test_header_carries_score_grade_and_counts(self, tmp_path: Path) -> None:
        """Header must expose grade, score/100 and pass/fail counts."""
        from axm_init.core.checker import format_agent_text

        result = _make_result(tmp_path, passed=True, score=100)
        text = format_agent_text(result)
        header = text.splitlines()[0]
        assert "init_check" in header
        assert "A 100/100" in header
        assert "1 ok" in header
        assert "0 fail" in header

    def test_all_passed_states_success_without_failures(self, tmp_path: Path) -> None:
        """No failures → a single success line, no ✗ markers."""
        from axm_init.core.checker import format_agent_text

        result = _make_result(tmp_path, passed=True)
        text = format_agent_text(result)
        assert "All gold-standard checks passed." in text
        assert "✗" not in text

    def test_failure_keeps_name_message_details_and_fix(self, tmp_path: Path) -> None:
        """Every failed check must keep its name, message, detail and fix."""
        from axm_init.core.checker import format_agent_text

        result = _make_result(tmp_path, passed=False)
        text = format_agent_text(result)
        assert "✗ test.check" in text
        assert "missing" in text  # message
        assert "detail line" in text  # detail (verbatim, not dropped)
        assert "Run fix command" in text  # fix (verbatim)
        assert "1 fail" in text
