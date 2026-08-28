"""Unit tests for console-script resolution."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from axm_ingot.console import console_script


def test_a_script_next_to_the_interpreter_wins(tmp_path: Path) -> None:
    """The environment's own entry point is preferred over anything on PATH."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    (bindir / "mytool").write_text("#!/bin/sh\n", encoding="utf-8")

    resolved = console_script("mytool", executable=str(bindir / "python"))

    assert resolved == str(bindir / "mytool")


def test_it_falls_back_to_path_then_to_the_bare_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An absent script degrades to PATH, then to the name itself.

    Returning the bare name rather than raising keeps the caller's own error
    (``FileNotFoundError`` at exec time) intact instead of masking it here.
    """
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))

    resolved = console_script("absent-tool", executable=str(empty / "python"))

    assert resolved == "absent-tool"


def test_it_defaults_to_the_running_interpreter() -> None:
    """With no explicit interpreter, the current environment is searched."""
    resolved = console_script("python")

    assert resolved.endswith("python")
    assert resolved == str(Path(sys.executable).parent / "python")
