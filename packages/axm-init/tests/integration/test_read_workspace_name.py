"""Split from ``test_scaffold_tool_error_paths_and_member.py``."""

from pathlib import Path

import pytest


@pytest.mark.parametrize(
    ("toml_body", "expected"),
    [
        pytest.param(None, None, id="fallback-to-dirname"),
        pytest.param('[project]\nname = "my-ws"\n', "my-ws", id="from-toml"),
    ],
)
def test_read_workspace_name(
    tmp_path: Path, toml_body: str | None, expected: str | None
) -> None:
    """read_workspace_name reads pyproject.toml or falls back to dir name."""
    from axm_init.tools.scaffold import read_workspace_name

    if toml_body is not None:
        (tmp_path / "pyproject.toml").write_text(toml_body)
    result = read_workspace_name(tmp_path)
    assert result == (expected if expected is not None else tmp_path.name)
