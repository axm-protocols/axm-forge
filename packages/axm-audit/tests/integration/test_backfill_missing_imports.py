"""Integration tests for backfill_missing_imports (real tmp_path I/O)."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.core.fix.cst_rewrite import backfill_missing_imports

pytestmark = pytest.mark.integration


def test_backfill_missing_imports_copies_from_source(tmp_path: Path) -> None:
    source = tmp_path / "source.py"
    source.write_text("from pkg import helper\n\n\ndef test_a():\n    helper()\n")
    target = tmp_path / "target.py"
    target.write_text("def test_b():\n    helper()\n")
    msgs = backfill_missing_imports(source, target)
    text = target.read_text()
    assert "from pkg import helper" in text
    assert any("backfilled import for `helper`" in m for m in msgs)


def test_backfill_missing_imports_reports_unresolved(tmp_path: Path) -> None:
    source = tmp_path / "source.py"
    source.write_text("def test_a():\n    pass\n")
    target = tmp_path / "target.py"
    target.write_text("def test_b():\n    mystery_symbol()\n")
    msgs = backfill_missing_imports(source, target)
    assert any("unresolved import for `mystery_symbol`" in m for m in msgs)


def test_backfill_missing_imports_missing_target_returns_empty(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.py"
    source.write_text("from pkg import helper\n")
    target = tmp_path / "absent.py"
    assert backfill_missing_imports(source, target) == []


def test_backfill_missing_imports_into_type_checking_block(tmp_path: Path) -> None:
    """A donor import living in a ``if TYPE_CHECKING:`` block is replayed there."""
    source = tmp_path / "source.py"
    source.write_text(
        "from typing import TYPE_CHECKING\n\n"
        "if TYPE_CHECKING:\n"
        "    from pkg import Widget\n"
    )
    target = tmp_path / "target.py"
    target.write_text("def test_b(obj: Widget) -> None:\n    assert obj\n")
    msgs = backfill_missing_imports(source, target)
    text = target.read_text()
    assert "if TYPE_CHECKING:" in text
    assert "from pkg import Widget" in text
    assert any("backfilled import for `Widget`" in m for m in msgs)


def test_backfill_missing_imports_merges_into_existing_tc_block(
    tmp_path: Path,
) -> None:
    """A TC-bucket donor merges into the target's pre-existing TYPE_CHECKING block."""
    source = tmp_path / "source.py"
    source.write_text(
        "from typing import TYPE_CHECKING\n\n"
        "if TYPE_CHECKING:\n"
        "    from pkg import Gadget\n"
    )
    target = tmp_path / "target.py"
    target.write_text(
        "from typing import TYPE_CHECKING\n\n"
        "if TYPE_CHECKING:\n"
        "    from pkg import Existing\n\n"
        "def test_b(a: Existing, b: Gadget) -> None:\n    assert a and b\n"
    )
    backfill_missing_imports(source, target)
    text = target.read_text()
    # Both names live under a SINGLE TYPE_CHECKING block (merge, not a new block).
    assert text.count("if TYPE_CHECKING:") == 1
    assert "from pkg import Gadget" in text
    assert "from pkg import Existing" in text


def test_backfill_missing_imports_malformed_target_is_noop(tmp_path: Path) -> None:
    """A target that fails to ast-parse yields no backfill and no crash."""
    source = tmp_path / "source.py"
    source.write_text("from pkg import helper\n")
    target = tmp_path / "target.py"
    original = "def test_b(:\n    helper()\n"
    target.write_text(original)
    assert backfill_missing_imports(source, target, project_path=tmp_path) == []
    assert target.read_text() == original
