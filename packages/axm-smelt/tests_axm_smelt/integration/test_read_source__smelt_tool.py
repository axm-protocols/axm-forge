from __future__ import annotations

from pathlib import Path

import pytest

from axm_smelt.core.counter import count
from axm_smelt.tools.smelt import SmeltTool


@pytest.mark.integration
def test_smelt_uses_designated_file_content(tmp_path: Path) -> None:
    """AC2: smelt reports the original token count of a designated UTF-8 file."""
    content = "alpha beta gamma delta café"
    input_path = tmp_path / "probe.txt"
    input_path.write_text(content, encoding="utf-8")

    result = SmeltTool().execute(input_path=str(input_path))

    assert result.success
    assert isinstance(result.data, dict)
    assert result.data["original_tokens"] == count(content)
