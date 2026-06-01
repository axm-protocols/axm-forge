"""Integration tests for backfill_missing_imports (real tmp_path file I/O)."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.integration
def test_extend_recoverable_unresolved_name_no_keyerror(tmp_path: Path) -> None:
    """AC4: a name the backfill genuinely cannot resolve produces a warning
    list (no KeyError / opaque crash) when no donor exists in the project.
    """
    from axm_audit.core.fix.cst_rewrite import backfill_missing_imports

    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    source = tests_dir / "source.py"
    source.write_text("x = 1\n")
    target = tests_dir / "target.py"
    # References an unresolvable name with no import / definition / donor.
    target.write_text("def test_t() -> None:\n    assert TotallyUnknownName()\n")

    result = backfill_missing_imports(source, target, tmp_path)

    assert len(result) == 1
    assert "TotallyUnknownName" in result[0]
    assert "no donor found" in result[0]
