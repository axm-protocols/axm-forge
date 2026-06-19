"""Integration tests for axm_echo.scope.load_scope (real filesystem I/O).

These exercise the on-disk config contract (``~/axm/echo.toml``) and the
graceful-degradation fallback, so they write a real config file under a
``tmp_path`` HOME -- hence the integration tier, not unit.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_echo.scope import load_scope

pytestmark = pytest.mark.integration


# Each case is one way the config can be unusable; all must degrade to the
# cwd fallback rather than raise. ``None`` means "write no config file".
_DEGRADED_CONFIGS = [
    pytest.param(None, id="absent_file"),
    pytest.param("this is = = not toml\n", id="malformed_toml"),
    pytest.param('workspace_roots = "not-a-list"\n', id="non_list_value"),
]


@pytest.mark.parametrize("config_text", _DEGRADED_CONFIGS)
def test_unusable_config_falls_back_to_cwd(
    config_text: str | None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC5: every unusable-config shape degrades to the cwd, never raises."""
    monkeypatch.setenv("HOME", str(tmp_path))
    if config_text is not None:
        config_dir = tmp_path / "axm"
        config_dir.mkdir()
        (config_dir / "echo.toml").write_text(config_text, encoding="utf-8")
    cwd = tmp_path / "work"
    cwd.mkdir()
    monkeypatch.chdir(cwd)

    roots = load_scope()

    # No exception, and the current workspace is the only root.
    assert roots == [cwd.resolve()]


def test_reads_workspace_roots(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AC5: workspace_roots declared in ~/axm/echo.toml are read."""
    monkeypatch.setenv("HOME", str(tmp_path))
    config_dir = tmp_path / "axm"
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


def test_non_string_entries_within_list_are_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A list mixing a valid path with a non-string keeps only the path."""
    monkeypatch.setenv("HOME", str(tmp_path))
    config_dir = tmp_path / "axm"
    config_dir.mkdir()
    root_a = tmp_path / "ws_a"
    root_a.mkdir()
    (config_dir / "echo.toml").write_text(
        f'workspace_roots = ["{root_a}", 42]\n', encoding="utf-8"
    )

    roots = load_scope()

    assert roots == [root_a.resolve()]
