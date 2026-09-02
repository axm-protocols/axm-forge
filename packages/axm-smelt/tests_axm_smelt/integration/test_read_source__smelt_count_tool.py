from __future__ import annotations

from pathlib import Path

import pytest

from axm_smelt.core.counter import count
from axm_smelt.tools.check import SmeltCheckTool
from axm_smelt.tools.count import SmeltCountTool
from axm_smelt.tools.smelt import SmeltTool


@pytest.mark.integration
def test_count_uses_designated_file_content(tmp_path: Path) -> None:
    """AC1: a designated UTF-8 file is counted from its content, not its path."""
    content = "alpha beta gamma delta café"
    input_path = tmp_path / "probe.txt"
    input_path.write_text(content, encoding="utf-8")

    result = SmeltCountTool().execute(input_path=str(input_path))

    assert result.success
    assert isinstance(result.data, dict)
    assert result.data["tokens"] == count(content)
    assert result.data["tokens"] != count(str(input_path))


@pytest.mark.integration
def test_missing_designated_file_fails_for_every_tool(tmp_path: Path) -> None:
    """AC4: every tool rejects a missing input path and names that exact path."""
    input_path = tmp_path / "absent.txt"

    for tool in (SmeltCountTool(), SmeltTool(), SmeltCheckTool()):
        result = tool.execute(input_path=str(input_path))

        assert not result.success
        assert result.error is not None
        assert str(input_path) in result.error
