"""Integration test: compose the render primitives into a full compact text."""

from __future__ import annotations

import pytest

from axm_ingot.render import compact_table, header, labeled_block, truncate

pytestmark = pytest.mark.integration


def test_full_compact_text_assembled_from_composed_primitives() -> None:
    summary = truncate("audited 3 files, 2 findings across the workspace", 60)
    top = header("audit", summary)
    block = labeled_block("Findings", ["complexity: 1", "security: 1"])
    table = compact_table(
        [["src/a.py", "complexity"], ["src/b.py", "security"]],
        headers=["file", "rule"],
    )
    text = "\n".join([top, block, table])

    lines = text.splitlines()
    assert lines[0] == top
    assert text.index("Findings") < text.index("src/a.py")
    assert "src/a.py" in text
    assert "file" in text and "rule" in text
    assert text.startswith("audit | ")
