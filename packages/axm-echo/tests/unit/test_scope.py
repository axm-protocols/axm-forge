"""Unit tests for axm_echo.scope."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_echo.scope import load_scope


def test_missing_config_falls_back_to_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC5: absent config degrades gracefully to the current workspace."""
    monkeypatch.setenv("HOME", str(tmp_path))
    cwd = tmp_path / "work"
    cwd.mkdir()
    monkeypatch.chdir(cwd)

    roots = load_scope()

    # No exception, and the current workspace is the only root.
    assert roots == [cwd.resolve()]


def test_reads_workspace_roots(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AC5: workspace_roots declared in ~/.axm/echo.toml are read."""
    monkeypatch.setenv("HOME", str(tmp_path))
    config_dir = tmp_path / ".axm"
    config_dir.mkdir()
    root_a = tmp_path / "ws_a"
    root_b = tmp_path / "ws_b"
    root_a.mkdir()
    root_b.mkdir()
    (config_dir / "echo.toml").write_text(
        f'workspace_roots = ["{root_a}", "{root_b}"]\n',
        encoding="utf-8",
    )

    roots = load_scope()

    assert root_a.resolve() in roots
    assert root_b.resolve() in roots
