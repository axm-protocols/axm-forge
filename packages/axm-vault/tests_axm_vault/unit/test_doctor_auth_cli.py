"""CLI renders authentication provenance without a credential value."""

import pytest

from axm_vault import cli


def test_doctor_renders_session_status_and_login(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        cli,
        "doctor_data",
        lambda *args, **kwargs: {
            "harness.auth.cursor-agent": {
                "layer": "auth-session",
                "present": False,
                "status": "disconnected",
                "login_command": "cursor-agent login",
            },
        },
    )
    cli.doctor()
    assert capsys.readouterr().out.strip() == (
        "harness.auth.cursor-agent\tauth-session\t-\tdisconnected"
        "\tlogin: cursor-agent login"
    )
