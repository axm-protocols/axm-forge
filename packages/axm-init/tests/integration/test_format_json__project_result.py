"""Split from ``test_check_engine_run_and_format.py``."""

from pathlib import Path

from axm_init.core.checker import format_json
from axm_init.models.check import CheckResult, ProjectResult


class TestFormatJsonContext:
    """Format JSON includes context fields."""

    def test_format_json_context(self, tmp_path: Path) -> None:
        """JSON output includes context, workspace_root."""
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
        result = ProjectResult.from_checks(tmp_path, checks, context="workspace")
        data = format_json(result)
        assert data["context"] == "workspace"
        assert "excluded_checks" in data
