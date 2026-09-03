"""Integration coverage for tool secret-location detection."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.core.rules.practices import tool_secret_locations

pytestmark = pytest.mark.integration

_MODULES = {
    "auth_session_path.py": ('CLAUDE_SESSION_PATH = "~/.claude/.credentials.json"\n'),
    "auth_keyring_service.py": (
        "import keyring\n\n"
        'user = "probe"\n'
        'CREDENTIAL = keyring.get_password("Claude Code-credentials", user)\n'
    ),
    "auth_probe_only.py": (
        'import subprocess\n\nSTATUS = subprocess.run(["gh", "auth", "status"])\n'
    ),
    "auth_internal_paths.py": (
        "import keyring\n\n"
        'SESSION_PATH = "~/.probe_pkg/credentials.json"\n'
        'user = "probe"\n'
        'CREDENTIAL = keyring.get_password("probe_pkg-credentials", user)\n'
    ),
}


def _build_project(root: Path, *module_names: str) -> Path:
    """Create an audited src-layout project from the requested module bodies."""
    package_dir = root / "src" / "probe_pkg"
    auth_dir = package_dir / "auth"
    auth_dir.mkdir(parents=True)
    (package_dir / "__init__.py").write_text("", encoding="utf-8")
    (auth_dir / "__init__.py").write_text("", encoding="utf-8")
    for module_name in module_names:
        (auth_dir / module_name).write_text(_MODULES[module_name], encoding="utf-8")
    return root


def test_third_party_session_path_is_reported(tmp_path: Path) -> None:
    """AC1: report a third-party session-file path in an auth module."""
    project = _build_project(tmp_path, "auth_session_path.py")

    result = tool_secret_locations.ToolSecretLocationRule().check(project)

    assert result.passed is False
    assert result.text is not None
    assert "auth_session_path.py" in result.text
    assert "~/.claude/.credentials.json" in result.text


def test_third_party_keyring_service_is_reported(tmp_path: Path) -> None:
    """AC2: report a third-party keyring service in an auth module."""
    project = _build_project(tmp_path, "auth_keyring_service.py")

    result = tool_secret_locations.ToolSecretLocationRule().check(project)

    assert result.passed is False
    assert result.text is not None
    assert "auth_keyring_service.py" in result.text
    assert "Claude Code-credentials" in result.text


def test_only_third_party_secret_locations_are_reported(tmp_path: Path) -> None:
    """AC3: report both offenders but neither a probe nor internal paths."""
    project = _build_project(tmp_path, *_MODULES)

    namespaces = tool_secret_locations.first_party_namespaces(project)
    result = tool_secret_locations.ToolSecretLocationRule().check(project)

    assert {"probe_pkg", "probe"} <= namespaces
    assert result.passed is False
    assert result.text is not None
    named_modules = {
        module_name for module_name in _MODULES if module_name in result.text
    }
    assert named_modules == {
        "auth_session_path.py",
        "auth_keyring_service.py",
    }
