"""Split from ``test_workspace_checks.py``."""

from pathlib import Path

from axm_init.checks.workspace import check_matrix_packages


class TestMatrixPackages:
    """Tests for check_matrix_packages."""

    def test_valid(self, ws_root: Path) -> None:
        """CI yml with --package passes."""
        ci = ws_root / ".github" / "workflows"
        ci.mkdir(parents=True)
        (ci / "ci.yml").write_text(
            "jobs:\n  test:\n    run: uv run pytest --package pkg-a\n"
        )
        result = check_matrix_packages(ws_root)
        assert result.passed

    def test_missing(self, ws_root: Path) -> None:
        """CI yml without --package fails."""
        ci = ws_root / ".github" / "workflows"
        ci.mkdir(parents=True)
        (ci / "ci.yml").write_text("jobs:\n  test:\n    run: pytest\n")
        result = check_matrix_packages(ws_root)
        assert not result.passed

    def test_no_ci(self, ws_root: Path) -> None:
        """No CI workflows fails gracefully."""
        result = check_matrix_packages(ws_root)
        assert not result.passed
        assert "not found" in result.message
