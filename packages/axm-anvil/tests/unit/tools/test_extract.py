from __future__ import annotations

from axm_anvil.tools.extract import ExtractTool


def test_name_is_anvil_extract() -> None:
    """AC2: the tool exposes the ``anvil_extract`` registry name."""
    assert ExtractTool().name == "anvil_extract"
