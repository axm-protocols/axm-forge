"""Split from ``test_check_engine_run_and_format.py``."""

from pathlib import Path

from axm_init.models.check import CheckResult, ProjectResult


class TestProjectResultContext:
    """ProjectResult context fields."""

    def test_project_result_context_field(self, tmp_path: Path) -> None:
        """Context field is stored and accessible."""
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
        result = ProjectResult.from_checks(
            tmp_path, checks, context="workspace", workspace_root=tmp_path
        )
        assert result.context == "workspace"
        assert result.workspace_root == tmp_path
        assert result.excluded_checks == []
