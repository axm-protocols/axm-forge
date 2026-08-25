"""Integration tests for axm_doctor.detect auth resolution (real filesystem).

These exercise :func:`axm_doctor.detect.detect_auth` against a real temp HOME
(``tmp_path``) and a real credential file on disk, so they live at the
integration level rather than alongside the pure-stdlib unit detect tests.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_doctor.detect import AuthStatus, detect_auth


@pytest.mark.integration
def test_detect_auth_logged_out_gives_login_cmd(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """AC3, AC4: missing credential file -> logged_out + login_cmd, no token field."""
    # Pin off-darwin so claude resolves via the credential-file branch
    # deterministically (on macOS it would consult the Keychain instead).
    monkeypatch.setattr("axm_doctor.detect.sys.platform", "linux")
    monkeypatch.setattr(Path, "home", classmethod(lambda _cls: tmp_path))

    status = detect_auth("claude")

    assert status.state == "logged_out"
    assert status.login_cmd
    assert "claude" in status.login_cmd
    assert "token" not in AuthStatus.model_fields


@pytest.mark.integration
def test_detect_auth_never_reads_token(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """AC3: detect_auth never reads the credential file content (no token leakage)."""
    secret = "SECRET_TOKEN_VALUE_DO_NOT_LEAK_abcdef123456"
    cred_dir = tmp_path / ".codex"
    cred_dir.mkdir(parents=True)
    (cred_dir / "auth.json").write_text(f'{{"token": "{secret}"}}')
    monkeypatch.setattr(Path, "home", classmethod(lambda _cls: tmp_path))

    status = detect_auth("codex")

    serialized = status.model_dump_json()
    assert secret not in serialized
    assert status.state == "logged_in"
