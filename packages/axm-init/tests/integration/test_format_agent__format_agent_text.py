"""Split from ``test_check_engine_run_and_format.py``."""

from pathlib import Path

from axm_init.models.check import CheckResult, ProjectResult
from tests.integration._helpers import _make_result


class TestFormatAgentCompactDictShape:
    """Compact agent output exposes score/grade/counts and drops the 'passed' key."""

    def test_format_agent_all_passed(self, tmp_path: Path) -> None:
        """All passing → failures=[], passed_count is count of checks."""
        from axm_init.core.checker import format_agent

        result = _make_result(tmp_path, passed=True)
        output = format_agent(result)
        assert output["failures"] == []
        assert output["passed_count"] == 1
        assert isinstance(output["passed_count"], int)

    def test_format_agent_with_failures(self, tmp_path: Path) -> None:
        """Failed items must have name, message, details, fix."""
        from axm_init.core.checker import format_agent

        result = _make_result(tmp_path, passed=False)
        output = format_agent(result)
        assert len(output["failures"]) == 1
        f = output["failures"][0]
        assert set(f.keys()) >= {"name", "message", "details", "fix"}

    def test_format_agent_has_required_keys(self, tmp_path: Path) -> None:
        """Agent output must have score, grade, context, passed_count, failures."""
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
            "failures",
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
        assert "failures" in output


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
