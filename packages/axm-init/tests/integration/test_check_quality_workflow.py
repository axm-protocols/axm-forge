"""Split from ``test_workspace_checks.py``."""

from pathlib import Path

from axm_init.checks.workspace import check_quality_workflow


class TestQualityWorkflow:
    """Tests for check_quality_workflow."""

    def test_quality_workflow_present(self, ws_root: Path) -> None:
        """axm-quality.yml with audit + coverage passes."""
        ci = ws_root / ".github" / "workflows"
        ci.mkdir(parents=True)
        (ci / "axm-quality.yml").write_text(
            "name: axm-quality\njobs:\n  quality:\n"
            "    run: axm-audit\n    coverage: true\n"
        )
        result = check_quality_workflow(ws_root)
        assert result.passed

    def test_quality_workflow_missing(self, ws_root: Path) -> None:
        """No axm-quality.yml → fails."""
        result = check_quality_workflow(ws_root)
        assert not result.passed
        assert "not found" in result.message


class TestQualityWorkflowPartial:
    """Cover lines 462-468: workflow exists but missing audit or coverage."""

    def test_missing_audit(self, tmp_path: Path) -> None:
        """Workflow without audit reference → fails."""
        from axm_init.checks.workspace import check_quality_workflow

        ci = tmp_path / ".github" / "workflows"
        ci.mkdir(parents=True)
        (ci / "axm-quality.yml").write_text(
            "name: quality\njobs:\n  check:\n    run: coverage report\n"
        )
        result = check_quality_workflow(tmp_path)
        assert not result.passed
        assert "audit" in (result.message or "")

    def test_missing_coverage(self, tmp_path: Path) -> None:
        """Workflow without coverage reference → fails."""
        from axm_init.checks.workspace import check_quality_workflow

        ci = tmp_path / ".github" / "workflows"
        ci.mkdir(parents=True)
        (ci / "axm-quality.yml").write_text(
            "name: quality\njobs:\n  check:\n    run: axm-audit check\n"
        )
        result = check_quality_workflow(tmp_path)
        assert not result.passed
        assert "coverage" in (result.message or "")

    def test_missing_both(self, tmp_path: Path) -> None:
        """Workflow without audit or coverage → both flagged."""
        from axm_init.checks.workspace import check_quality_workflow

        ci = tmp_path / ".github" / "workflows"
        ci.mkdir(parents=True)
        (ci / "axm-quality.yml").write_text(
            "name: quality\njobs:\n  check:\n    run: echo hello\n"
        )
        result = check_quality_workflow(tmp_path)
        assert not result.passed
        assert "audit" in (result.message or "")
        assert "coverage" in (result.message or "")
