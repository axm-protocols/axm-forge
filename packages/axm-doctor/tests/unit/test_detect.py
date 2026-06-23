"""Unit tests for axm_doctor.detect (pure-stdlib tool/auth detection)."""

from __future__ import annotations

import subprocess

import pytest
from pydantic import ValidationError

from axm_doctor.detect import ToolStatus, detect_tool


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
