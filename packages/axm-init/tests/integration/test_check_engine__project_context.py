"""Split from ``test_check_engine_run_and_format.py``."""

from pathlib import Path

from axm_init.checks._workspace import ProjectContext
from axm_init.core.checker import CheckEngine


class TestEngineMember:
    """Member context redirects CI/tooling to workspace root."""

    def test_engine_member_redirects_ci(
        self, tmp_path: Path, gold_project__from_check_engine_run_and_format: Path
    ) -> None:
        """Member CI checks run against workspace root."""
        # Create workspace structure: tmp_path is workspace root
        ws_root = tmp_path / "workspace"
        ws_root.mkdir()
        (ws_root / "pyproject.toml").write_text(
            '[project]\nname = "ws"\n[tool.uv.workspace]\nmembers = ["packages/*"]\n'
        )

        # Create member package
        member = ws_root / "packages" / "pkg"
        member.mkdir(parents=True)
        (member / "pyproject.toml").write_text('[project]\nname = "pkg"\n')

        engine = CheckEngine(member)
        assert engine.context == ProjectContext.MEMBER
        assert engine.workspace_root == ws_root
