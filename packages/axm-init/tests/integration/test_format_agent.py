"""Split from ``test_check_engine_run_and_format.py``."""

from pathlib import Path

from axm_init.models.check import CheckResult, ProjectResult
from tests.integration._helpers import _make_result


class TestFormatAgent:
    """Tests for format_agent() — compact agent output."""

    def test_format_agent_all_passed(self, tmp_path: Path) -> None:
        """All passing → failed=[], passed_count is count of checks."""
        from axm_init.core.checker import format_agent

        result = _make_result(tmp_path, passed=True)
        output = format_agent(result)
        assert output["failed"] == []
        assert output["passed_count"] == 1
        assert isinstance(output["passed_count"], int)

    def test_format_agent_with_failures(self, tmp_path: Path) -> None:
        """Failed items must have name, message, details, fix."""
        from axm_init.core.checker import format_agent

        result = _make_result(tmp_path, passed=False)
        output = format_agent(result)
        assert len(output["failed"]) == 1
        f = output["failed"][0]
        assert set(f.keys()) >= {"name", "message", "details", "fix"}

    def test_format_agent_has_required_keys(self, tmp_path: Path) -> None:
        """Agent output must have score, grade, context, passed_count, failed."""
        from axm_init.core.checker import format_agent

        result = _make_result(tmp_path, passed=True)
        output = format_agent(result)
        assert set(output.keys()) == {
            "score",
            "grade",
            "context",
            "workspace_root",
            "excluded_checks",
            "passed_count",
            "failed",
        }

    def test_format_agent_no_passed_key(self, tmp_path: Path) -> None:
        """Agent output must NOT have a 'passed' key (replaced by count)."""
        from axm_init.core.checker import format_agent

        result = _make_result(tmp_path, passed=True)
        output = format_agent(result)
        assert "passed" not in output


def _make_project_result(
    tmp_path: Path,
    *,
    context: str = "workspace",
    workspace_root: Path | None = None,
    excluded_checks: list[str] | None = None,
) -> ProjectResult:
    """Build a minimal ProjectResult with context info."""
    check = CheckResult(
        name="test.dummy",
        category="test",
        passed=True,
        weight=10,
        message="OK",
        details=[],
        fix="",
    )
    return ProjectResult.from_checks(
        tmp_path,
        [check],
        context=context,
        workspace_root=workspace_root or tmp_path,
        excluded_checks=excluded_checks or ["ci.ci_workflow_exists"],
    )


class TestFormatAgentIncludesContext:
    """AC5: format_agent includes context, workspace_root, excluded_checks."""

    def test_format_agent_all_context_fields(self, tmp_path: Path) -> None:
        from axm_init.core.checker import format_agent

        result = _make_project_result(
            tmp_path,
            context="member",
            workspace_root=tmp_path.parent,
            excluded_checks=["ci.ci_workflow_exists", "tooling.makefile"],
        )

        output = format_agent(result)

        assert output["context"] == "member"
        assert output["workspace_root"] == str(tmp_path.parent)
        assert output["excluded_checks"] == [
            "ci.ci_workflow_exists",
            "tooling.makefile",
        ]
        assert "score" in output
        assert "grade" in output
        assert "passed_count" in output
        assert "failed" in output
