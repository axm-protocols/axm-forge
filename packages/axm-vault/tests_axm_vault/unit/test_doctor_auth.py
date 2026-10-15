"""Value-free CLI authentication diagnostics."""

import json

import pytest

from axm_vault.auth import AuthDependencySpec, AuthStatus
from axm_vault.catalog import Catalog
from axm_vault.doctor import doctor_data
from axm_vault.models import CredentialGroup


class SessionSource:
    """Expose presence without any credential-reading API."""

    def __init__(self, state: AuthStatus) -> None:
        self.state = state
        self.calls = 0

    def status(self) -> AuthStatus:
        self.calls += 1
        return self.state


@pytest.mark.parametrize("state", list(AuthStatus))
def test_doctor_reports_cli_dependencies(state: AuthStatus) -> None:
    source = SessionSource(state)
    dependencies = tuple(
        AuthDependencySpec(name=name, source=source, login_command=f"{name} login")
        for name in ("claude", "codex", "cursor-agent")
    )
    catalog = Catalog(
        groups=(
            CredentialGroup(
                id="harness",
                package="axm-harness",
                title="Harness",
                specs=(),
                auth_dependencies=dependencies,
            ),
        )
    )
    report = doctor_data("axm-harness", catalog=catalog)
    for dependency in dependencies:
        entry = report[f"harness.auth.{dependency.name}"]
        assert entry["layer"] == "auth-session"
        assert entry["status"] == state.value
        assert entry["present"] is (state is AuthStatus.CONNECTED)
        assert entry["login_command"] == dependency.login_command
    assert source.calls == 3
    assert "token" not in json.dumps(report)
    assert doctor_data("unrelated", catalog=catalog) == {}
