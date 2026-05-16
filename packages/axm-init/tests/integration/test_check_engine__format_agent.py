"""Split from ``test_cli_workspace_scaffold_subcommands.py``."""

from pathlib import Path


def test_format_agent_has_context(
    workspace_root__from_cli_workspace_scaffold_subcommands: Path,
) -> None:
    """Agent output includes context field."""
    from axm_init.core.checker import CheckEngine, format_agent

    engine = CheckEngine(workspace_root__from_cli_workspace_scaffold_subcommands)
    result = engine.run()
    agent_output = format_agent(result)

    assert "context" in agent_output
    assert agent_output["context"] == "workspace"
