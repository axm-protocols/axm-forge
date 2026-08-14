"""Split from ``test_check_engine_run_and_format.py``."""

from pathlib import Path

from axm_init.checks._workspace import ProjectContext
from axm_init.core import checker
from axm_init.core.checker import CheckEngine


def _skip_table() -> dict[ProjectContext, frozenset[str]]:
    """The context-keyed skip table the check engine must expose (AC1)."""
    table: dict[ProjectContext, frozenset[str]] | None = getattr(
        checker, "SKIP_BY_CONTEXT", None
    )
    assert table is not None, "axm_init.core.checker must expose SKIP_BY_CONTEXT"
    return table


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
        for skip_name in _skip_table()[ProjectContext.WORKSPACE]:
            assert skip_name not in check_names, (
                f"{skip_name} should be skipped for workspace"
            )
