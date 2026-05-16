"""Split from ``test_cli_workspace_scaffold_subcommands.py``."""

from pathlib import Path
from typing import Any


def test_cli_check_shows_context(
    workspace_root__from_cli_workspace_scaffold_subcommands: Path, capsys: Any
) -> None:
    """check on workspace shows 'Context: WORKSPACE'."""
    from axm_init.core.checker import CheckEngine

    engine = CheckEngine(workspace_root__from_cli_workspace_scaffold_subcommands)
    result = engine.run()

    from axm_init.core.checker import format_report

    report = format_report(result)
    assert "Context:" in report
    assert "WORKSPACE" in report
