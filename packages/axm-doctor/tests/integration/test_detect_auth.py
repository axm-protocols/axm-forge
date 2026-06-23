"""Integration tests for axm_doctor.detect credential-file probing (real I/O).

This exercises :func:`axm_doctor.detect.detect_auth` against a real temp HOME
(``tmp_path``) and a real 0-byte credential file on disk, so it lives at the
integration level rather than alongside the pure-stdlib unit detect tests.
"""

from __future__ import annotations

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
