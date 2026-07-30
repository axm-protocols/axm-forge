"""Tests for checks._workspace — workspace context detection."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_init.checks._workspace import (
    ProjectContext,
    detect_context,
)


@pytest.mark.parametrize(
    "content",
    [
        pytest.param(None, id="missing_pyproject"),
        pytest.param("{{invalid toml!!", id="corrupt_toml"),
    ],
)
def test_detect_context_falls_back_to_standalone(
    tmp_path: Path, content: str | None
) -> None:
    """Missing or corrupt pyproject.toml → STANDALONE (graceful fallback)."""
    if content is not None:
        (tmp_path / "pyproject.toml").write_text(content)
    assert detect_context(tmp_path) == ProjectContext.STANDALONE
