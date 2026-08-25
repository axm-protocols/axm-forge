"""Unit tests for the Svelte config gold-standard check."""

from __future__ import annotations

from pathlib import Path

from axm_init.checks.svelte.config import check_svelte_config


def test_svelte_config_present_passes(tmp_path: Path) -> None:
    """A svelte.config.js passes."""
    (tmp_path / "svelte.config.js").write_text("export default {};")
    assert check_svelte_config(tmp_path).passed is True


def test_svelte_config_absent_fails(tmp_path: Path) -> None:
    """No svelte.config fails."""
    assert check_svelte_config(tmp_path).passed is False
