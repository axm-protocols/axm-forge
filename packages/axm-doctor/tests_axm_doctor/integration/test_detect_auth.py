"""Integration tests for axm_doctor.detect credential-file probing (real I/O).

This exercises :func:`axm_doctor.detect.detect_auth` against a real temp HOME
(``tmp_path``) and a real 0-byte credential file on disk, so it lives at the
integration level rather than alongside the pure-stdlib unit detect tests.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from axm_doctor.detect import detect_auth

pytestmark = pytest.mark.integration


def test_empty_cred_file_not_logged_in(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pytest.TempPathFactory
) -> None:
    """AC4: a 0-byte credential file is NOT reported logged_in.

    The credential-file probe must not equate "the file exists" with "a token
    is present": an empty (0-byte) file carries no credentials, so the state
    must be ``logged_out`` (or any non-``logged_in`` state), never ``logged_in``.
    """
    # Pin the platform off-darwin so the file branch is exercised
    # deterministically: on macOS, claude resolves via the Keychain instead.
    monkeypatch.setattr("axm_doctor.detect.sys.platform", "linux")
    home = Path(str(tmp_path))
    cred = home / ".claude" / ".credentials.json"
    cred.parent.mkdir(parents=True)
    cred.write_text("")  # 0-byte credential file
    monkeypatch.setattr("axm_doctor.detect.Path.home", lambda: home)

    status = detect_auth("claude")

    assert status.state != "logged_in"


def test_claude_non_darwin_uses_file_branch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """AC2: off macOS, claude keeps the credential-file branch (no keychain call)."""
    monkeypatch.setattr("axm_doctor.detect.sys.platform", "linux")
    cred = tmp_path / ".claude" / ".credentials.json"
    cred.parent.mkdir(parents=True)
    cred.write_text('{"token": "x"}')
    monkeypatch.setattr("axm_doctor.detect.Path.home", lambda: tmp_path)

    def _fail(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("keychain probe must not run off-darwin")

    monkeypatch.setattr("axm_doctor.detect.subprocess.run", _fail)

    status = detect_auth("claude")

    assert status.state == "logged_in"


def test_claude_darwin_keychain_absent_falls_back_to_cred_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """macOS: an absent Keychain entry must fall back to the credential file.

    Regression guard for the darwin ``elif`` that short-circuited to the
    Keychain and NEVER consulted ``~/.claude/.credentials.json``: a file-backed
    session (container / CI / CLAUDE_CONFIG_DIR / locked Keychain) was
    mis-reported ``logged_out``. With a present credential file and a Keychain
    miss, the verdict must be ``logged_in``.
    """
    monkeypatch.setattr("axm_doctor.detect.sys.platform", "darwin")
    # Keychain lookup misses: ``security`` present but exit != 0.
    monkeypatch.setattr(
        "axm_doctor.detect.shutil.which", lambda _name: "/usr/bin/security"
    )
    monkeypatch.setattr(
        "axm_doctor.detect.subprocess.run",
        lambda *_a, **_k: subprocess.CompletedProcess(args=[], returncode=1),
    )
    cred = tmp_path / ".claude" / ".credentials.json"
    cred.parent.mkdir(parents=True)
    cred.write_text('{"token": "x"}')
    monkeypatch.setattr("axm_doctor.detect.Path.home", lambda: tmp_path)

    status = detect_auth("claude")

    assert status.state == "logged_in"


@pytest.mark.parametrize("platform", ["darwin", "linux"])
def test_codex_unchanged_file_branch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, platform: str
) -> None:
    """AC4: codex stays on the credential-file branch on both platforms."""
    monkeypatch.setattr("axm_doctor.detect.sys.platform", platform)
    cred = tmp_path / ".codex" / "auth.json"
    cred.parent.mkdir(parents=True)
    cred.write_text('{"token": "y"}')
    monkeypatch.setattr("axm_doctor.detect.Path.home", lambda: tmp_path)

    status = detect_auth("codex")

    assert status.state == "logged_in"
