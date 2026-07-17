"""Integration: `check --strict` reflects real detect/auth status.

Exercises the CLI ``check`` command end-to-end over the real detect layer
(``shutil.which`` + a subprocess ``gh auth status``) using an on-disk fake
binary and a restricted ``PATH`` — a genuine filesystem/subprocess boundary,
not a mock.
"""

from __future__ import annotations

import stat
from pathlib import Path

import pytest

import axm_doctor.cli as cli_mod

_FAKE_GH = """#!/bin/sh
case "$1" in
  --version) echo "gh version 2.0.0" ;;
  auth) exit 1 ;;
  *) exit 1 ;;
esac
"""


@pytest.mark.integration
def test_strict_signals_failure_on_logged_out_auth(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC2: a real logged_out `gh` (auth status rc!=0) makes strict exit 1."""
    gh = tmp_path / "gh"
    gh.write_text(_FAKE_GH)
    gh.chmod(gh.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    # Restrict PATH to the fake-binary dir: gh resolves (and reports logged_out
    # via its rc!=1 auth-status), every other probed tool is genuinely absent.
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.setattr(cli_mod, "missing_secrets", list)

    with pytest.raises(SystemExit) as exc_info:
        cli_mod.check(strict=True)

    assert exc_info.value.code == 1
