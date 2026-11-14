"""Runtime reads may inspect files but never prepare storage or start workers."""

from __future__ import annotations

import importlib

import pytest

from axm_config import NamespaceStore, get, get_file_namespace, resolution_origin
from axm_config.doctor import config_doctor_data
from axm_config.home import axm_data_path, axm_home_path, axm_state_path
from axm_config.paths import sessions_root
from axm_config.profile import profile_config_path, profile_env


@pytest.fixture
def forbid_effects(monkeypatch):
    """Fail on attempted writes or execution, even if a caller catches them."""
    import builtins
    import io
    import os
    import socket
    import sqlite3
    import subprocess
    import sys
    import threading

    # Import bytecode is interpreter bookkeeping, not runtime state preparation.
    monkeypatch.setattr(sys, "dont_write_bytecode", True)
    attempts = []

    def deny(*args, **kwargs):
        attempts.append("effect")
        raise AssertionError("read-only boundary attempted a write or execution")

    def guarded_open(original):
        def read_only(file, mode="r", *args, **kwargs):
            if any(flag in mode for flag in "wax+"):
                deny()
            return original(file, mode, *args, **kwargs)

        return read_only

    monkeypatch.setattr(builtins, "open", guarded_open(builtins.open))
    monkeypatch.setattr(io, "open", guarded_open(io.open))
    original_os_open = os.open

    def read_only_os_open(path, flags, *args, **kwargs):
        if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
            deny()
        return original_os_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", read_only_os_open)
    for name in (
        "mkdir",
        "makedirs",
        "chmod",
        "remove",
        "unlink",
        "rmdir",
        "rename",
        "replace",
        "system",
    ):
        monkeypatch.setattr(os, name, deny)
    for name in (
        "utime",
        "chown",
        "link",
        "symlink",
        "truncate",
        "fork",
        "posix_spawn",
        "posix_spawnp",
    ):
        monkeypatch.setattr(os, name, deny, raising=False)
    for name in ("connect", "bind", "listen"):
        monkeypatch.setattr(socket.socket, name, deny)
    monkeypatch.setattr(sqlite3, "connect", deny)
    monkeypatch.setattr(subprocess, "Popen", deny)
    monkeypatch.setattr(threading.Thread, "start", deny)
    yield attempts
    assert attempts == []


@pytest.mark.parametrize("present", [False, True])
def test_config_reads_under_effect_guard(tmp_path, monkeypatch, request, present):
    root = tmp_path / "installation"
    if present:
        root.mkdir()
        (root / "config.toml").write_text('[demo]\nkey="value"\n')
    monkeypatch.setenv("AXM_ROOT", str(root))
    monkeypatch.setenv("AXM_PROFILE", "production")
    monkeypatch.delenv("AXM_HOME", raising=False)
    request.getfixturevalue("forbid_effects")
    importlib.reload(importlib.import_module("axm_config.paths"))
    assert get("demo", "key") == ("value" if present else None)
    assert get_file_namespace("demo") == ({"key": "value"} if present else {})
    assert NamespaceStore(strict_reads=True).read("demo") == (
        {"key": "value"} if present else {}
    )
    assert resolution_origin("demo", "key", strict=True)["layer"] == (
        "file" if present else "default"
    )
    assert config_doctor_data("demo") == (
        {"demo.key": {"layer": "file", "present": True}} if present else {}
    )
    assert sessions_root() == root / "data/sessions"
    assert axm_home_path() == root
    assert axm_state_path("orison") == root / "state/orison"
    assert axm_data_path("sessions") == root / "data/sessions"
    assert profile_config_path() == root / "config.toml"
    assert profile_env()["AXM_ROOT"] == str(root)
