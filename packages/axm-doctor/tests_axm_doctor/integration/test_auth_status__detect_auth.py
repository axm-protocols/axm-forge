"""Integration tests for the public authentication-status tool."""

from __future__ import annotations

import importlib
from importlib import metadata
from pathlib import Path

import pytest

from axm_doctor import AuthStatusTool, collect_credential_provenance, detect_auth
from axm_doctor.detect import load_auth_declarations


@pytest.mark.integration
def test_auth_status_publishes_live_credential_provenance() -> None:
    """AC1: auth_status publishes exactly the live credential coordinates."""
    expected_rows = collect_credential_provenance()

    result = AuthStatusTool().execute()

    assert result.success is True
    credentials = result.data["credentials"]
    assert set(credentials) == {row.coordinate for row in expected_rows}
    assert all(set(entry) == {"layer", "present"} for entry in credentials.values())


@pytest.mark.integration
def test_auth_status_separates_undetermined_from_logged_out(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC1: auth_status separates undetermined tools from logged-out tools."""
    import shutil

    import axm_doctor.tools as tools_mod

    assert shutil.which("sh") is not None
    monkeypatch.setattr(tools_mod, "THIRD_PARTY_AUTH", ("sh",))

    result = AuthStatusTool().execute()

    assert result.success is True
    assert result.data["undetermined"] == ["sh"]
    assert "sh" not in result.data["logged_out"]


@pytest.mark.integration
def test_auth_status_marks_tools_without_discovered_declaration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC2: text marks undeclared tools and leaves the declared tool unmarked."""
    module_path = tmp_path / "synthetic_auth.py"
    module_path.write_text(
        "from axm_vault import AuthDependencySpec, AuthStatus, CredentialGroup\n\n"
        "class ConnectedSource:\n"
        "    def status(self):\n"
        "        return AuthStatus.CONNECTED\n\n"
        "def credentials():\n"
        "    dependency = AuthDependencySpec(\n"
        "        name='claude', source=ConnectedSource()\n"
        "    )\n"
        "    return (CredentialGroup(\n"
        "        id='synthetic', package='synthetic-auth', title='Synthetic',\n"
        "        specs=(), auth_dependencies=(dependency,),\n"
        "    ),)\n",
        encoding="utf-8",
    )
    dist_info = tmp_path / "synthetic_auth-1.0.dist-info"
    dist_info.mkdir()
    (dist_info / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: synthetic-auth\nVersion: 1.0\n",
        encoding="utf-8",
    )
    (dist_info / "entry_points.txt").write_text(
        "[axm.credentials]\nsynthetic = synthetic_auth:credentials\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    importlib.invalidate_caches()
    synthetic_endpoints = tuple(
        endpoint
        for distribution in metadata.distributions(path=[str(tmp_path)])
        for endpoint in distribution.entry_points
        if endpoint.group == "axm.credentials"
    )

    def _synthetic_entry_points(*, group: str) -> tuple[metadata.EntryPoint, ...]:
        return tuple(
            endpoint for endpoint in synthetic_endpoints if endpoint.group == group
        )

    monkeypatch.setattr(metadata, "entry_points", _synthetic_entry_points)
    assert set(load_auth_declarations()) == {"claude"}
    declared_status = detect_auth("claude")

    result = AuthStatusTool().execute()

    assert result.success is True
    auth_lines = result.text.split("\n\n", maxsplit=1)[0].splitlines()[1:]
    lines = {
        line.removeprefix("- ").split(":", maxsplit=1)[0]: line for line in auth_lines
    }
    assert set(lines) == {"gh", "claude", "codex"}
    assert all(
        result.data["auth"][tool]["state"] in line for tool, line in lines.items()
    )
    assert "[no declaration]" in lines["gh"]
    assert "[no declaration]" not in lines["claude"]
    assert declared_status.state in lines["claude"]
    assert "[no declaration]" in lines["codex"]
