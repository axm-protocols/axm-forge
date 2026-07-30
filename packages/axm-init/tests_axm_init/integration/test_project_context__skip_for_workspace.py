"""Split from ``test_check_engine_run_and_format.py``."""

from pathlib import Path

from axm_init.checks._workspace import ProjectContext
from axm_init.core.checker import CheckEngine


class TestEngineWorkspace:
    """Workspace context skips package-only checks."""

    def test_engine_workspace_skips_package_checks(
        self, gold_project__from_check_engine_run_and_format: Path
    ) -> None:
        """Workspace fixture skips SKIP_FOR_WORKSPACE checks."""
        # Add workspace section to make it a workspace root
        pyproject = gold_project__from_check_engine_run_and_format / "pyproject.toml"
        content = pyproject.read_text()
        content += '\n[tool.uv.workspace]\nmembers = ["packages/*"]\n'
        pyproject.write_text(content)

        engine = CheckEngine(gold_project__from_check_engine_run_and_format)
        assert engine.context == ProjectContext.WORKSPACE

        result = engine.run()
        check_names = {c.name for c in result.checks}
        from axm_init.core.checker import SKIP_FOR_WORKSPACE

        for skip_name in SKIP_FOR_WORKSPACE:
            assert skip_name not in check_names, (
                f"{skip_name} should be skipped for workspace"
            )
