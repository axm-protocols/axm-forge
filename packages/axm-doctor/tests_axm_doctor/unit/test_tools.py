"""Unit tests for axm_doctor.tools — env_doctor / auth_status MCP tools."""

from __future__ import annotations

import dataclasses

import pytest

from axm_doctor.credentials import CredentialProvenance
from axm_doctor.detect import AuthStatus, GhConfigStatus, GitIdentityStatus, ToolStatus
from axm_doctor.orchestrate import MissingSecret
from axm_doctor.tools import AuthStatusTool, EnvDoctorTool


def test_env_doctor_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC1: EnvDoctorTool returns success with tools + auth + missing secrets."""
    import axm_doctor.tools as tools_mod

    monkeypatch.setattr(
        tools_mod,
        "detect_tool",
        lambda name: ToolStatus(name=name, state="present", version="1.0"),
    )
    monkeypatch.setattr(
        tools_mod,
        "detect_auth",
        lambda tool: AuthStatus(tool=tool, state="logged_in"),
    )
    monkeypatch.setattr(
        tools_mod,
        "missing_secrets",
        lambda: [
            MissingSecret(
                group="svc",
                name="token",
                package="pkg",
                setup_hint="axm-vault set svc.token",
                required=True,
            )
        ],
    )

    result = EnvDoctorTool().execute()

    assert result.success is True
    assert "tools" in result.data
    assert "auth" in result.data
    assert "secrets" in result.data
    assert result.data["secrets"][0]["group"] == "svc"


def test_env_doctor_failure_on_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC1: any error at the MCP boundary becomes a failure ToolResult."""
    import axm_doctor.tools as tools_mod

    def _boom() -> list[MissingSecret]:
        msg = "vault unreachable"
        raise RuntimeError(msg)

    monkeypatch.setattr(tools_mod, "missing_secrets", _boom)

    result = EnvDoctorTool().execute()

    assert result.success is False
    assert result.error is not None


def test_env_doctor_name() -> None:
    """AC1: EnvDoctorTool advertises the env_doctor identifier."""
    assert EnvDoctorTool().name == "env_doctor"


def test_auth_status_no_token_in_result(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC2: the serialized auth_status ToolResult carries NO token value."""
    import axm_doctor.tools as tools_mod

    # Even if a buggy detector leaked a secret-looking login_cmd, the tool's
    # contract is that the serialized result never contains a token value.
    monkeypatch.setattr(
        tools_mod,
        "detect_auth",
        lambda tool: AuthStatus(
            tool=tool, state="logged_out", login_cmd=f"{tool} login"
        ),
    )

    result = AuthStatusTool().execute()

    assert result.success is True
    serialized = str(dataclasses.asdict(result))
    assert "SECRET_TOKEN_VALUE" not in serialized
    # The data is shaped as {tool: {state, login_cmd}} — never a token key.
    for entry in result.data["auth"].values():
        assert "token" not in entry
        assert set(entry) <= {"state", "login_cmd"}


def test_auth_status_name() -> None:
    """AC2: AuthStatusTool advertises the auth_status identifier."""
    assert AuthStatusTool().name == "auth_status"


def test_env_doctor_exposes_config_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC1, AC5: env_doctor adds a value-free 'config' key (git+gh) additively.

    The existing tools/auth/secrets keys stay present, git joins PROBED_TOOLS,
    and the new config map reports git + gh state without any value.
    """
    import axm_doctor.tools as tools_mod

    monkeypatch.setattr(
        tools_mod,
        "detect_tool",
        lambda name: ToolStatus(name=name, state="present", version="1.0"),
    )
    monkeypatch.setattr(
        tools_mod,
        "detect_auth",
        lambda tool: AuthStatus(tool=tool, state="logged_in"),
    )
    monkeypatch.setattr(tools_mod, "missing_secrets", lambda: [])
    monkeypatch.setattr(
        tools_mod,
        "detect_git_identity",
        lambda: GitIdentityStatus(state="configured"),
    )
    monkeypatch.setattr(
        tools_mod,
        "detect_gh_config",
        lambda: GhConfigStatus(state="configured"),
    )

    result = EnvDoctorTool().execute()

    assert result.success is True
    # Existing keys remain present (additive change).
    assert {"tools", "auth", "secrets"} <= set(result.data)
    # git joined the probed tools.
    assert "git" in result.data["tools"]
    # New config map carries git + gh state, value-free.
    config = result.data["config"]
    assert config["git"]["state"] == "configured"
    assert config["gh"]["state"] == "configured"


def test_credentials_map_preserves_layers_and_value_free_shape() -> None:
    """AC2: all provenance layers remain distinct and value-free."""
    import axm_doctor.tools as tools_mod

    rows = [
        CredentialProvenance(
            coordinate="a.one", kind="token", layer="env", present=True
        ),
        CredentialProvenance(
            coordinate="b.two", kind="password", layer="file", present=True
        ),
        CredentialProvenance(
            coordinate="c.three", kind="token", layer="missing", present=False
        ),
    ]

    credentials = tools_mod._credentials_map(rows)

    assert credentials == {
        "a.one": {"kind": "token", "layer": "env", "present": True},
        "b.two": {"kind": "password", "layer": "file", "present": True},
        "c.three": {"kind": "token", "layer": "missing", "present": False},
    }
    assert all(
        set(entry) == {"kind", "layer", "present"} for entry in credentials.values()
    )


def test_credentials_text_names_coordinates_and_only_supplied_layers() -> None:
    """AC3: each coordinate is followed by its layer and no other layer."""
    import axm_doctor.tools as tools_mod

    credentials = {
        "a.one": {"kind": "token", "layer": "env", "present": True},
        "b.two": {"kind": "password", "layer": "file", "present": True},
    }

    rendered = tools_mod._credentials_text(credentials)

    lines = rendered.splitlines()
    assert any(
        "a.one" in line and "env" in line and line.index("a.one") < line.index("env")
        for line in lines
    )
    assert any(
        "b.two" in line and "file" in line and line.index("b.two") < line.index("file")
        for line in lines
    )
    assert all(layer not in rendered for layer in ("keyring", "default", "prompt"))


def test_credentials_rendering_groups_rows_by_declared_kind() -> None:
    """AC5: credentials and auth dependencies render under distinct kinds."""
    import axm_doctor.tools as tools_mod

    rows = [
        CredentialProvenance(
            coordinate="service.api_token",
            kind="token",
            layer="env",
            present=True,
        ),
        CredentialProvenance(
            coordinate="github.session",
            kind="auth_dependency",
            layer="disconnected",
            present=False,
        ),
    ]

    entries = tools_mod._credentials_map(rows)
    rendered = tools_mod._credentials_text(entries)

    assert entries["service.api_token"]["kind"] == "token"
    assert entries["github.session"]["kind"] == "auth_dependency"
    assert "token" in rendered
    assert "service.api_token" in rendered
    assert "auth_dependency" in rendered
    auth_line = next(line for line in rendered.splitlines() if "github.session" in line)
    assert "axm-vault set" not in auth_line
