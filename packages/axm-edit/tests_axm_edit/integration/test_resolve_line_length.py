"""Integration tests for the on-disk line-length resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_edit.services.line_length import resolve_line_length


@pytest.mark.integration
def test_resolved_pyproject_line_length_is_returned(tmp_path: Path) -> None:
    """AC5: the value declared in the root pyproject.toml wins."""
    (tmp_path / "pyproject.toml").write_text("[tool.ruff]\nline-length = 100\n")

    assert resolve_line_length(tmp_path) == 100


@pytest.mark.integration
def test_missing_pyproject_falls_back_to_88(tmp_path: Path) -> None:
    """AC5: with no pyproject.toml found, the fallback is 88."""
    assert resolve_line_length(tmp_path) == 88
