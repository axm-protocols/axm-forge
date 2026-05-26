from __future__ import annotations

import pytest

from axm_anvil.tools.move import MoveTool


@pytest.mark.integration
def test_tool_execute_exposes_shared_helpers_data(tmp_path):
    source = tmp_path / "src.py"
    target = tmp_path / "tgt.py"
    source.write_text(
        "def _shared():\n    return 1\n\n"
        "def moved_A():\n    return _shared()\n\n"
        "def remaining_B():\n    return _shared()\n"
    )
    target.write_text("")

    tool = MoveTool()
    result = tool.execute(
        path=str(tmp_path),
        symbols="moved_A",
        from_file="src.py",
        to_file="tgt.py",
    )
    assert result.success
    shared_data = result.data["shared_helpers_detected"]
    assert len(shared_data) == 1
    entry = shared_data[0]
    assert entry["name"] == "_shared"
    assert "moved_A" in entry["used_by_moved"]
    assert "remaining_B" in entry["used_by_remaining"]
