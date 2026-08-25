"""Integration tests for ``axm_echo.scope.load_scope`` (real shared config).

These exercise the on-disk contract through axm-config: a real
``~/.axm/config.toml`` (HOME pointed at a ``tmp_path``) holding an ``[echo]``
section, and the graceful-degradation fallback. Real filesystem I/O -> the
integration tier, not unit.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_echo.scope import load_scope

pytestmark = pytest.mark.integration


def _write_shared_config(home: Path, body: str | None) -> None:
    """Write ``~/.axm/config.toml`` under ``home`` with ``body`` (None -> none)."""
    if body is None:
        return
    axm_dir = home / ".axm"
    axm_dir.mkdir(parents=True, exist_ok=True)
    (axm_dir / "config.toml").write_text(body, encoding="utf-8")


def test_scope_reads_shared_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC3, AC6: workspace_roots read from the shared config.toml [echo] section."""
    home = tmp_path / "home"
    home.mkdir()
    root_a = tmp_path / "ws_a"
    root_b = tmp_path / "ws_b"
    root_a.mkdir()
    root_b.mkdir()
    monkeypatch.setenv("HOME", str(home))
    _write_shared_config(
        home,
        f'[echo]\nworkspace_roots = ["{root_a}", "{root_b}"]\n',
    )

    roots = load_scope()

    assert root_a.resolve() in roots
    assert root_b.resolve() in roots


# Each case is one way the shared config can be unusable; all must degrade to
# the cwd fallback rather than raise. ``None`` means "write no config file".
_DEGRADED_CONFIGS = [
    pytest.param(None, id="absent_file"),
    pytest.param("this is = = not toml\n", id="malformed_toml"),
    pytest.param("[echo]\n", id="missing_key"),
    pytest.param('[echo]\nworkspace_roots = "not-a-list"\n', id="non_list_value"),
]


@pytest.mark.parametrize("body", _DEGRADED_CONFIGS)
def test_unusable_config_falls_back_to_cwd(
    body: str | None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC3: every unusable shared-config shape degrades to cwd, never raises."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    _write_shared_config(home, body)
    cwd = tmp_path / "work"
    cwd.mkdir()
    monkeypatch.chdir(cwd)

    roots = load_scope()

    assert roots == [cwd.resolve()]
