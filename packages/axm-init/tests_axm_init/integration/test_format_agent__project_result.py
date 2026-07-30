"""Split from ``test_check_engine_run_and_format.py``."""

from pathlib import Path

from axm_init.models.check import CheckResult, ProjectResult


class TestFormatAgentContext:
    """Format agent includes context fields."""

    def test_format_agent_context(self, tmp_path: Path) -> None:
        """Agent output includes context."""
        from axm_init.core.checker import format_agent

        checks = [
            CheckResult(
                name="t.check",
                category="t",
                passed=True,
                weight=10,
                message="ok",
                details=[],
                fix="",
            )
        ]
        result = ProjectResult.from_checks(tmp_path, checks, context="member")
        output = format_agent(result)
        assert output["context"] == "member"
