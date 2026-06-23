from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from axm_config.store import NamespaceStore

pytestmark = pytest.mark.integration


def test_write_then_read_roundtrip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC1, AC2: a written value persists and is read back."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    store = NamespaceStore()
    store.write("app", "token", "secret")
    assert store.read("app") == {"token": "secret"}


def test_written_file_is_0600(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AC3: the written namespace file has mode ``0600``."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    store = NamespaceStore()
    store.write("app", "token", "secret")
    ns_file = tmp_path / ".axm" / "app.toml"
    assert stat.S_IMODE(ns_file.stat().st_mode) == 0o600


def test_write_preserves_other_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC2: read-modify-write keeps pre-existing keys."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    store = NamespaceStore()
    store.write("app", "first", "one")
    store.write("app", "second", "two")
    assert store.read("app") == {"first": "one", "second": "two"}


def test_read_missing_namespace_returns_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC1: reading an absent namespace returns ``{}`` without raising."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    store = NamespaceStore()
    assert store.read("nope") == {}


def test_read_corrupt_toml_returns_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC4: a corrupt/malformed TOML degrades gracefully to ``{}``."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    axm_dir = tmp_path / ".axm"
    axm_dir.mkdir(parents=True, exist_ok=True)
    (axm_dir / "broken.toml").write_bytes(b"this is = not [ valid toml ===")
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
    """AC5: write/delete unlink the temp file when ``os.replace`` raises.

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
