from __future__ import annotations

import importlib
from pathlib import Path
from types import ModuleType

import pytest


def _gh_auth_module() -> ModuleType:
    return importlib.import_module("axm_git.core.gh_auth")


def _install_gh_stub(directory: Path, *, returncode: int) -> None:
    executable = directory / "gh"
    executable.write_text(
        f"#!/bin/sh\nexit {returncode}\n",
        encoding="utf-8",
    )
    executable.chmod(0o755)


@pytest.mark.integration
def test_gh_auth_state_reports_not_installed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC1: The probe reports not_installed when PATH contains no gh."""
    monkeypatch.setenv("PATH", str(tmp_path))
    gh_auth = _gh_auth_module()

    assert gh_auth.gh_auth_state() == "not_installed"


@pytest.mark.integration
def test_gh_auth_state_reports_logged_out(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC2: The probe reports logged_out when a real gh stub exits non-zero."""
    _install_gh_stub(tmp_path, returncode=1)
    monkeypatch.setenv("PATH", str(tmp_path))
    gh_auth = _gh_auth_module()

    assert gh_auth.gh_auth_state() == "logged_out"


@pytest.mark.integration
def test_gh_auth_state_reports_logged_in(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC3: The probe reports logged_in when a real gh stub exits zero."""
    _install_gh_stub(tmp_path, returncode=0)
    monkeypatch.setenv("PATH", str(tmp_path))
    gh_auth = _gh_auth_module()

    assert gh_auth.gh_auth_state() == "logged_in"
