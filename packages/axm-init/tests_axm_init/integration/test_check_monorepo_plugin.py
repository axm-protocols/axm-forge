"""Split from ``test_workspace_checks.py``."""

from pathlib import Path

from axm_init.checks.workspace import check_monorepo_plugin


class TestMonorepoPlugin:
    """Tests for check_monorepo_plugin."""

    def test_present(self, ws_root: Path) -> None:
        """mkdocs.yml with monorepo plugin passes."""
        (ws_root / "mkdocs.yml").write_text("plugins:\n  - monorepo\n  - search\n")
        result = check_monorepo_plugin(ws_root)
        assert result.passed

    def test_missing(self, ws_root: Path) -> None:
        """mkdocs.yml without monorepo fails."""
        (ws_root / "mkdocs.yml").write_text("plugins:\n  - search\n")
        result = check_monorepo_plugin(ws_root)
        assert not result.passed

    def test_no_mkdocs(self, ws_root: Path) -> None:
        """No mkdocs.yml fails."""
        result = check_monorepo_plugin(ws_root)
        assert not result.passed
        assert "not found" in result.message
