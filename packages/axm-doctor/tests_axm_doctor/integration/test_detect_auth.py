"""Integration tests for declaration-driven authentication detection."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

import axm_doctor.detect as detect_module
from axm_doctor.detect import detect_auth

pytestmark = pytest.mark.integration

_FORBIDDEN_AUTH_LITERALS = (
    ".claude/.credentials.json",
    ".codex/auth.json",
    "Claude Code-credentials",
    "gh auth login",
    "claude login",
    "codex login",
)


def _detect_source() -> str:
    module_path = Path(detect_module.__file__)
    return module_path.read_text(encoding="utf-8")


def _install_auth_declaration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider_source = "\n".join(
        (
            "from __future__ import annotations",
            "",
            "import os",
            "",
            "from axm_vault import AuthDependencySpec, CredentialGroup",
            "",
            "",
            "class _Source:",
            "    def status(self) -> str:",
            '        return os.environ["AXM_TEST_DECLARED_AUTH_STATE"]',
            "",
            "",
            "def provide() -> tuple[CredentialGroup, ...]:",
            "    dependency = AuthDependencySpec(",
            '        name="declaration-only-tool",',
            "        source=_Source(),",
            "    )",
            "    return (",
            "        CredentialGroup(",
            '            id="declaration-only",',
            '            package="declaration-only",',
            '            title="Declaration only",',
            "            specs=(),",
            "            auth_dependencies=(dependency,),",
            "        ),",
            "    )",
            "",
        )
    )
    (tmp_path / "declaration_provider.py").write_text(
        provider_source,
        encoding="utf-8",
    )
    dist_info = tmp_path / "declaration_only-1.0.dist-info"
    dist_info.mkdir()
    (dist_info / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: declaration-only\nVersion: 1.0\n",
        encoding="utf-8",
    )
    (dist_info / "entry_points.txt").write_text(
        "[axm.credentials]\ndeclaration-only = declaration_provider:provide\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    importlib.invalidate_caches()


def test_detector_module_holds_no_third_party_auth_literal() -> None:
    """AC1: detect.py owns no session path, keychain name, or login command."""
    source = _detect_source()

    assert all(literal not in source for literal in _FORBIDDEN_AUTH_LITERALS)


def test_declaration_alone_drives_all_three_auth_states(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC2: an installed declaration alone drives every tri-state verdict."""
    _install_auth_declaration(tmp_path, monkeypatch)

    cases = (
        ("connected", "logged_in"),
        ("disconnected", "logged_out"),
        ("tool_absent", "not_installed"),
    )
    for observed, expected in cases:
        monkeypatch.setenv("AXM_TEST_DECLARED_AUTH_STATE", observed)
        assert detect_auth("declaration-only-tool").state == expected

    assert "_LOGIN_CMDS" not in _detect_source()
