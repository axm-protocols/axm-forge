from __future__ import annotations

from pathlib import Path

import pytest

from axm_smelt.core.counter import count
from axm_smelt.tools.check import SmeltCheckTool
from axm_smelt.tools.count import SmeltCountTool
from axm_smelt.tools.smelt import SmeltTool


@pytest.mark.integration
def test_check_uses_designated_file_content(tmp_path: Path) -> None:
    """AC3: check reports the original token count of a designated UTF-8 file."""
    content = "alpha beta gamma delta café"
    input_path = tmp_path / "probe.txt"
    input_path.write_text(content, encoding="utf-8")

    result = SmeltCheckTool().execute(input_path=str(input_path))

    assert result.success
    assert isinstance(result.data, dict)
    assert result.data["tokens"] == count(content)


@pytest.mark.integration
def test_invalid_utf8_fails_for_every_tool(tmp_path: Path) -> None:
    """AC5: every tool rejects invalid UTF-8 and names the designated path."""
    input_path = tmp_path / "latin.bin"
    input_path.write_bytes(b"\xff\xfe caf\xe9")

    for tool in (SmeltCountTool(), SmeltTool(), SmeltCheckTool()):
        result = tool.execute(input_path=str(input_path))

        assert not result.success
        assert result.error is not None
        assert str(input_path) in result.error
