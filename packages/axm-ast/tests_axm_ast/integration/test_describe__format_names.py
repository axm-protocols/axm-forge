from __future__ import annotations

from pathlib import Path

import pytest

from axm_ast.cli import describe

PACKAGE_ROOT = Path(__file__).parents[2]


@pytest.mark.integration
def test_describe_names_keeps_private_names(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The real-tree names index includes CLI private helpers (AC1)."""
    describe(str(PACKAGE_ROOT), detail="names")

    output = capsys.readouterr().out
    assert "## cli" in output
    bare_lines = {line.strip() for line in output.splitlines()}
    assert "_resolve_dir" in bare_lines
    assert "_print_toc" in bare_lines


@pytest.mark.integration
def test_describe_names_applies_modules_filter(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The names index preserves the formatters-only module filter (AC3)."""
    describe(str(PACKAGE_ROOT), detail="names", modules="formatters")

    output = capsys.readouterr().out
    assert "## formatters" in output
    assert "## cli" not in output
