from __future__ import annotations

import os
import stat
import tomllib
from pathlib import Path

import pytest
import tomli_w

from axm_config import UnsafeHomeError
from axm_config.store import NamespaceStore

pytestmark = pytest.mark.integration


def test_read_raises_unsafe_home_error_when_home_in_git_repo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """P0-3: a HOME resolving inside a git checkout raises UnsafeHomeError.

    ``resolve_safe`` refuses an ``~/.axm`` inside a git repo with a raw
    ``ValueError``; the store must re-type that as ``UnsafeHomeError`` (a
    ``ConfigError``) so a consumer of ``read``/``get`` gets the documented
    error contract rather than an unhandled ``ValueError``.
    """
    (tmp_path / ".git").mkdir()
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    store = NamespaceStore()

    with pytest.raises(UnsafeHomeError):
        store.read("demo")


def test_write_then_read_roundtrip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC1, AC2: a written value persists and is read back."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    store = NamespaceStore()
    store.write("app", "token", "secret")
    assert store.read("app") == {"token": "secret"}


def test_written_file_is_0600(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AC3: the single config.toml has mode ``0600``."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    store = NamespaceStore()
    store.write("app", "token", "secret")
    config = tmp_path / ".axm" / "config.toml"
    assert stat.S_IMODE(config.stat().st_mode) == 0o600


def test_write_preserves_other_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC2: read-modify-write keeps pre-existing keys in the same section."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    store = NamespaceStore()
    store.write("app", "first", "one")
    store.write("app", "second", "two")
    assert store.read("app") == {"first": "one", "second": "two"}


def test_read_missing_namespace_returns_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC4: reading an absent namespace returns ``{}`` without raising."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    store = NamespaceStore()
    assert store.read("nope") == {}


def test_read_corrupt_toml_returns_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC4: a corrupt/malformed config.toml degrades gracefully to ``{}``."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    axm_dir = tmp_path / ".axm"
    axm_dir.mkdir(parents=True, exist_ok=True)
    (axm_dir / "config.toml").write_bytes(b"this is = not [ valid toml ===")
    store = NamespaceStore()
    assert store.read("broken") == {}


def _axm_tmp_files(home: Path) -> list[Path]:
    """Return the temp files NamedTemporaryFile would leave under ``~/.axm``."""
    axm_dir = home / ".axm"
    if not axm_dir.exists():
        return []
    return [p for p in axm_dir.iterdir() if p.name.startswith("tmp")]


def test_temp_file_cleaned_on_replace_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC3: write/delete unlink the temp file when ``os.replace`` raises.

    The atomic write stages a same-dir ``NamedTemporaryFile`` and moves it in
    via ``os.replace``. If the move raises, the staged temp file must not leak
    under ``~/.axm`` (a ``try/finally`` unlinks it). Forcing ``os.replace`` to
    raise and asserting no orphan ``tmp*`` file remains pins that contract for
    both ``write`` and ``delete``.
    """
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    real_replace = os.replace

    def _boom(*_args: object, **_kwargs: object) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr(os, "replace", _boom)
    store = NamespaceStore()

    with pytest.raises(OSError, match="replace failed"):
        store.write("app", "token", "secret")
    assert _axm_tmp_files(tmp_path) == []

    # delete rewrites via the same staged-temp + os.replace path; seed two keys
    # (popping one leaves a non-empty mapping, so the rewrite branch runs).
    monkeypatch.setattr(os, "replace", real_replace)
    store.write("app", "token", "secret")
    store.write("app", "other", "value")
    monkeypatch.setattr(os, "replace", _boom)

    with pytest.raises(OSError, match="replace failed"):
        store.delete("app", "token")
    assert _axm_tmp_files(tmp_path) == []


def test_single_file_0600_atomic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC3: every namespace lands in a single config.toml, mode 0600, atomic.

    Two namespaces are written; the on-disk surface is exactly one
    ``config.toml`` (no per-namespace file, no leftover temp) at mode 0600.
    """
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    store = NamespaceStore()
    store.write("echo", "threshold", 0.5)
    store.write("linear", "team", "AXM")

    axm_dir = tmp_path / ".axm"
    config = axm_dir / "config.toml"
    assert config.exists()
    assert stat.S_IMODE(config.stat().st_mode) == 0o600
    assert not (axm_dir / "echo.toml").exists()
    assert not (axm_dir / "linear.toml").exists()
    leftovers = [p for p in axm_dir.iterdir() if p.name != "config.toml"]
    assert leftovers == []


def test_read_excludes_child_namespace_subtable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """P0-2: a nested sub-table is a child namespace, not a key of the parent.

    With ``[a]`` carrying ``x`` and a nested ``[a.b]``, ``read('a')`` must
    return only ``a``'s own scalar keys (no ``b`` sub-table leaking as a value),
    while ``read('a.b')`` returns the child section. Regression for the dict
    leak that made ``get('a', 'b')`` return a whole sub-table.
    """
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    store = NamespaceStore()
    store.write("a", "x", 1)
    store.write("a.b", "y", 2)

    assert store.read("a") == {"x": 1}
    assert store.read("a.b") == {"y": 2}


def test_namespaces_enumerates_mixed_parent_and_child(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """P1-3: a node that is both a namespace and a prefix is fully enumerated.

    ``[a]`` with a direct key ``x`` plus a nested ``[a.b]`` must list *both*
    ``a`` and ``a.b`` -- the old leaf-only rule hid ``a.b`` whenever the parent
    carried its own keys.
    """
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    store = NamespaceStore()
    store.write("a", "x", 1)
    store.write("a.b", "y", 2)

    assert store.namespaces() == ["a", "a.b"]


def test_legacy_per_ns_file_folded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC7: a legacy ~/.axm/<ns>.toml is folded into config.toml, value kept."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    axm_dir = tmp_path / ".axm"
    axm_dir.mkdir(parents=True, exist_ok=True)
    (axm_dir / "echo.toml").write_bytes(
        tomli_w.dumps({"threshold": 0.9}).encode("utf-8")
    )

    store = NamespaceStore()
    # The legacy value is visible through the unified read.
    assert store.read("echo") == {"threshold": 0.9}

    # On the next write the legacy section is folded into config.toml.
    store.write("echo", "window", 10)

    config = axm_dir / "config.toml"
    with config.open("rb") as fh:
        raw = tomllib.load(fh)
    assert raw["echo"]["threshold"] == 0.9
    assert raw["echo"]["window"] == 10
