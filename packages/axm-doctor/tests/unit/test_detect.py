"""Unit tests for axm_doctor.detect (pure-stdlib tool/auth detection)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from pydantic import ValidationError

from axm_doctor.detect import (
    ToolStatus,
    detect_auth,
    detect_gh_config,
    detect_git_identity,
    detect_tool,
)


class _Proc:
    """Minimal stand-in for ``subprocess.CompletedProcess`` (exit code only)."""

    def __init__(self, returncode: int) -> None:
        self.returncode = returncode


def _which_security(_name: str) -> str:
    """Stub ``shutil.which`` resolving the ``security`` binary to a fixed path."""
    return "/usr/bin/security"


def test_detect_tool_present(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC1: detect_tool reports 'present' with parsed version when on PATH."""
    monkeypatch.setattr(
        "axm_doctor.detect.shutil.which",
        lambda name: f"/usr/local/bin/{name}",
    )

    def fake_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=["uv", "--version"],
            returncode=0,
            stdout="uv 0.5.1\n",
            stderr="",
        )

    monkeypatch.setattr("axm_doctor.detect.subprocess.run", fake_run)

    status = detect_tool("uv")

    assert status.state == "present"
    assert status.version is not None
    assert "0.5.1" in status.version
    assert status.path == "/usr/local/bin/uv"


def test_detect_tool_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC1: detect_tool reports 'absent' with no version and never raises."""
    monkeypatch.setattr("axm_doctor.detect.shutil.which", lambda _name: None)

    status = detect_tool("does-not-exist")

    assert status.state == "absent"
    assert status.version is None
    assert status.path is None


def test_tool_status_frozen() -> None:
    """AC2: ToolStatus is a frozen pydantic model — mutation raises."""
    status = ToolStatus(name="uv", state="present", version="0.5.1", path="/bin/uv")

    with pytest.raises(ValidationError):
        status.state = "absent"  # type: ignore[misc]


def test_probe_version_extracts_from_noisy_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC3: detect_tool extracts a clean version from a multi-line banner.

    A tool that prints a welcome banner before its version must not leak the
    whole banner as ``version`` — the dotted version is regex-extracted.
    """
    monkeypatch.setattr(
        "axm_doctor.detect.shutil.which",
        lambda name: f"/usr/local/bin/{name}",
    )

    def fake_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=["noisy", "--version"],
            returncode=0,
            stdout="Welcome\nv1.2.3\n",
            stderr="",
        )

    monkeypatch.setattr("axm_doctor.detect.subprocess.run", fake_run)

    status = detect_tool("noisy")

    assert status.state == "present"
    assert status.version == "1.2.3"
    assert "Welcome" not in (status.version or "")
    assert "\n" not in (status.version or "")


def test_probe_version_banner_not_partial(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC3: a single-line banner with several numbers yields the tool version.

    For output like ``Python 3.12 wrapper, tool 2.1.0`` an un-anchored search
    grabs the FIRST dotted number (``3.12``) — a wrong partial. The probe must
    anchor/last-match so the actual tool version (``2.1.0``) is returned.
    """
    monkeypatch.setattr(
        "axm_doctor.detect.shutil.which",
        lambda name: f"/usr/local/bin/{name}",
    )

    def fake_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=["tool", "--version"],
            returncode=0,
            stdout="Python 3.12 wrapper, tool 2.1.0\n",
            stderr="",
        )

    monkeypatch.setattr("axm_doctor.detect.subprocess.run", fake_run)

    status = detect_tool("tool")

    assert status.state == "present"
    assert status.version == "2.1.0"


def test_claude_darwin_keychain_present_is_logged_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC1: macOS Keychain entry present (exit 0) -> logged_in, no login hint."""
    monkeypatch.setattr("axm_doctor.detect.sys.platform", "darwin")
    monkeypatch.setattr("axm_doctor.detect.shutil.which", _which_security)
    monkeypatch.setattr("axm_doctor.detect.subprocess.run", lambda *a, **k: _Proc(0))

    status = detect_auth("claude")

    assert status.state == "logged_in"
    assert status.login_cmd is None


def test_claude_darwin_keychain_absent_is_logged_out(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC1, AC5: macOS Keychain entry absent (exit 1) -> logged_out + login hint."""
    monkeypatch.setattr("axm_doctor.detect.sys.platform", "darwin")
    monkeypatch.setattr("axm_doctor.detect.shutil.which", _which_security)
    monkeypatch.setattr("axm_doctor.detect.subprocess.run", lambda *a, **k: _Proc(1))

    status = detect_auth("claude")

    assert status.state == "logged_out"
    assert status.login_cmd == "claude login"


def test_claude_darwin_security_missing_degrades_logged_out(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC3: a missing ``security`` binary degrades to logged_out without raising."""
    monkeypatch.setattr("axm_doctor.detect.sys.platform", "darwin")
    monkeypatch.setattr("axm_doctor.detect.shutil.which", lambda _name: None)

    status = detect_auth("claude")

    assert status.state == "logged_out"


def test_claude_darwin_subprocess_error_degrades_logged_out(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC3: any OSError/SubprocessError from the probe degrades to logged_out."""
    monkeypatch.setattr("axm_doctor.detect.sys.platform", "darwin")
    monkeypatch.setattr("axm_doctor.detect.shutil.which", _which_security)

    def _boom(*_args: object, **_kwargs: object) -> _Proc:
        raise OSError("no security")

    monkeypatch.setattr("axm_doctor.detect.subprocess.run", _boom)

    status = detect_auth("claude")

    assert status.state == "logged_out"


def test_claude_non_darwin_uses_file_branch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """AC2: off macOS, claude keeps the credential-file branch (no keychain call)."""
    monkeypatch.setattr("axm_doctor.detect.sys.platform", "linux")
    cred = tmp_path / ".claude" / ".credentials.json"
    cred.parent.mkdir(parents=True)
    cred.write_text('{"token": "x"}')
    monkeypatch.setattr("axm_doctor.detect.Path.home", lambda: tmp_path)

    def _fail(*_args: object, **_kwargs: object) -> _Proc:
        raise AssertionError("keychain probe must not run off-darwin")

    monkeypatch.setattr("axm_doctor.detect.subprocess.run", _fail)

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


def test_git_identity_configured_via_store(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC2: a truthy ``[git].default`` in the store -> configured, no subprocess."""
    monkeypatch.setattr(
        "axm_doctor.detect.axm_config.get",
        lambda *_a, **_k: {"name": "Gabriel", "email": "g@example.com"},
    )

    def _no_subprocess(*_args: object, **_kwargs: object) -> _Proc:
        raise AssertionError("store hit must short-circuit the git subprocess")

    monkeypatch.setattr("axm_doctor.detect.subprocess.run", _no_subprocess)

    status = detect_git_identity()

    assert status.state == "configured"


def test_git_identity_configured_via_git_config_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC2: empty store but ``git config --get user.email`` exit 0 -> configured."""
    monkeypatch.setattr("axm_doctor.detect.axm_config.get", lambda *_a, **_k: None)
    monkeypatch.setattr("axm_doctor.detect.shutil.which", _which_security)
    monkeypatch.setattr("axm_doctor.detect.subprocess.run", lambda *a, **k: _Proc(0))

    status = detect_git_identity()

    assert status.state == "configured"


def test_git_identity_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC2: empty store and ``git config`` exit 1 -> unconfigured."""
    monkeypatch.setattr("axm_doctor.detect.axm_config.get", lambda *_a, **_k: None)
    monkeypatch.setattr("axm_doctor.detect.shutil.which", _which_security)
    monkeypatch.setattr("axm_doctor.detect.subprocess.run", lambda *a, **k: _Proc(1))

    status = detect_git_identity()

    assert status.state == "unconfigured"


def test_git_identity_subprocess_error_degrades(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC4: any OSError from the git probe degrades to unconfigured (no raise)."""
    monkeypatch.setattr("axm_doctor.detect.axm_config.get", lambda *_a, **_k: None)
    monkeypatch.setattr("axm_doctor.detect.shutil.which", _which_security)

    def _boom(*_args: object, **_kwargs: object) -> _Proc:
        raise OSError("no git")

    monkeypatch.setattr("axm_doctor.detect.subprocess.run", _boom)

    status = detect_git_identity()

    assert status.state == "unconfigured"


def test_gh_config_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC3: ``gh config get git_protocol`` exit 0 -> configured."""
    monkeypatch.setattr("axm_doctor.detect.shutil.which", _which_security)
    monkeypatch.setattr("axm_doctor.detect.subprocess.run", lambda *a, **k: _Proc(0))

    status = detect_gh_config()

    assert status.state == "configured"


def test_gh_config_not_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC3: gh absent from PATH -> not_installed (never reads a value)."""
    monkeypatch.setattr("axm_doctor.detect.shutil.which", lambda _name: None)

    status = detect_gh_config()

    assert status.state == "not_installed"
