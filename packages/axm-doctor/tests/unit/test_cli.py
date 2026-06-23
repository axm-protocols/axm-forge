"""Unit tests for axm_doctor.cli — check (read-only) + bootstrap (gated)."""

from __future__ import annotations

import pytest

from axm_doctor.cli import app


class _Tty:
    """Minimal interactive stdin stub: ``isatty()`` reports a real terminal."""

    def isatty(self) -> bool:
        return True


def test_check_never_installs(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC3: `check` prints the report, exits 0, and NEVER installs or prompts."""
    import axm_doctor.cli as cli_mod

    install_calls: list[object] = []
    monkeypatch.setattr(
        cli_mod, "run_install", lambda *a, **k: install_calls.append((a, k))
    )
    provision_calls: list[object] = []
    monkeypatch.setattr(
        cli_mod,
        "provision_missing",
        lambda *a, **k: provision_calls.append((a, k)),
    )

    def _no_input(*_a: object, **_k: object) -> str:
        msg = "check must never prompt"
        raise AssertionError(msg)

    monkeypatch.setattr("builtins.input", _no_input)
    monkeypatch.setattr(cli_mod, "missing_secrets", list)

    # cyclopts exits the process on completion; check is read-only -> exit 0.
    with pytest.raises(SystemExit) as exc_info:
        app(["check"])

    assert exc_info.value.code in (0, None)
    assert install_calls == []
    assert provision_calls == []
    out = capsys.readouterr().out
    assert "uv" in out


def test_bootstrap_no_install_on_decline(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC4: `bootstrap` installs nothing when the user declines (default No)."""
    import axm_doctor.cli as cli_mod
    from axm_doctor.detect import AuthStatus, ToolStatus
    from axm_doctor.install import InstallResult

    install_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def _spy_install(*a: object, **k: object) -> InstallResult:
        install_calls.append((a, k))
        return InstallResult(command="noop", executed=False)

    monkeypatch.setattr(cli_mod, "run_install", _spy_install)

    provision_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
    monkeypatch.setattr(
        cli_mod,
        "provision_missing",
        lambda *a, **k: provision_calls.append((a, k)),
    )

    # Force an absent tool so bootstrap *would* offer to install it.
    monkeypatch.setattr(
        cli_mod, "detect_tool", lambda name: ToolStatus(name=name, state="absent")
    )
    monkeypatch.setattr(
        cli_mod,
        "detect_auth",
        lambda tool: AuthStatus(tool=tool, state="logged_in"),
    )
    monkeypatch.setattr(cli_mod, "missing_secrets", list)
    # Interactive shell (a real TTY) so the install loop reaches its prompts.
    monkeypatch.setattr(cli_mod.sys, "stdin", _Tty())
    # Decline every prompt.
    monkeypatch.setattr("builtins.input", lambda *_a, **_k: "n")

    # cyclopts exits the process on completion; declining must still exit 0.
    with pytest.raises(SystemExit) as exc_info:
        app(["bootstrap"])

    assert exc_info.value.code in (0, None)
    # No install ever fires without an explicit yes: run_install is never
    # invoked with confirm=True (the no-system-install invariant).
    for _args, kwargs in install_calls:
        assert kwargs.get("confirm", False) is not True
    for _args, kwargs in provision_calls:
        assert kwargs.get("confirm", False) is not True


def test_bootstrap_reports_failed_install(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC3, AC4: a confirmed install that returns rc!=0 with the tool still
    absent is reported as failed (with the post-check state) — NEVER 'installed'
    merely because run_install executed."""
    import axm_doctor.cli as cli_mod
    from axm_doctor.detect import AuthStatus, ToolStatus
    from axm_doctor.install import InstallPlan, InstallResult

    plan = InstallPlan(tool="uv", argv=["true"], human_command="curl … | sh")

    def _failed_install(*_a: object, **_k: object) -> InstallResult:
        # executed=True but the command failed (rc=1) and the tool is still absent.
        return InstallResult(
            command=plan.human_command,
            executed=True,
            returncode=1,
            post_check=ToolStatus(name="uv", state="absent"),
        )

    monkeypatch.setattr(
        cli_mod, "detect_tool", lambda name: ToolStatus(name=name, state="absent")
    )
    monkeypatch.setattr(
        cli_mod, "detect_auth", lambda tool: AuthStatus(tool=tool, state="logged_in")
    )
    monkeypatch.setattr(cli_mod, "install_command", lambda _name: plan)
    monkeypatch.setattr(cli_mod, "run_install", _failed_install)
    monkeypatch.setattr(cli_mod, "missing_secrets", list)
    # Interactive shell (a real TTY) so the install loop reaches its prompts.
    monkeypatch.setattr(cli_mod.sys, "stdin", _Tty())
    # Confirm the install prompt (so run_install fires with confirm=True).
    monkeypatch.setattr("builtins.input", lambda *_a, **_k: "y")

    with pytest.raises(SystemExit) as exc_info:
        app(["bootstrap"])

    assert exc_info.value.code in (0, None)
    out = capsys.readouterr().out
    # AC4: a failed install must NOT be reported as installed.
    assert "installed" not in out
    assert "failed" in out


def test_bootstrap_surfaces_provision_reason(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC2: bootstrap surfaces provision_missing's reason/provisioned.

    When a confirmed provisioning does NOT actually provision (provisioned is
    False with a reason), the CLI must not swallow it silently: the user must
    see that the secret was NOT provisioned and why.
    """
    import axm_doctor.cli as cli_mod
    from axm_doctor.detect import AuthStatus, ToolStatus
    from axm_doctor.orchestrate import MissingSecret, ProvisionResult

    # No tool is absent -> the install loop is a no-op (focus on secrets).
    monkeypatch.setattr(
        cli_mod, "detect_tool", lambda name: ToolStatus(name=name, state="present")
    )
    monkeypatch.setattr(
        cli_mod, "detect_auth", lambda tool: AuthStatus(tool=tool, state="logged_in")
    )
    monkeypatch.setattr(
        cli_mod,
        "missing_secrets",
        lambda: [
            MissingSecret(
                group="openai",
                name="api_key",
                package="axm-llm",
                setup_hint="axm-vault set openai.api_key",
            )
        ],
    )
    reason = "non-interactive shell: cannot prompt for secrets"
    monkeypatch.setattr(
        cli_mod,
        "provision_missing",
        lambda **_k: ProvisionResult(
            provisioned=False, groups=["openai"], reason=reason
        ),
    )
    # Confirm the vault-setup prompt so provision_missing fires with confirm=True.
    monkeypatch.setattr("builtins.input", lambda *_a, **_k: "y")

    with pytest.raises(SystemExit) as exc_info:
        app(["bootstrap"])

    assert exc_info.value.code in (0, None)
    out = capsys.readouterr().out
    # The not-provisioned outcome and its reason must reach the user.
    assert reason in out


def test_bootstrap_tools_non_tty_skips_clean(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC1, AC2, AC3: on a non-TTY stdin the tool-install loop reports a clean
    'non-interactive, skipping installs' message and skips installs.

    No ``EOFError`` escapes to the ``_die`` boundary (which would exit 1 with a
    traceback-shaped message); the run exits cleanly and ``run_install`` never
    fires with ``confirm=True`` — mirroring ``provision_missing``'s non-TTY
    handling.
    """
    import axm_doctor.cli as cli_mod
    from axm_doctor.detect import AuthStatus, ToolStatus
    from axm_doctor.install import InstallPlan, InstallResult
    from axm_doctor.orchestrate import ProvisionResult

    plan = InstallPlan(tool="uv", argv=["true"], human_command="curl … | sh")
    install_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def _spy_install(*a: object, **k: object) -> InstallResult:
        install_calls.append((a, k))
        return InstallResult(command=plan.human_command, executed=False)

    # An absent tool with a known install command: the loop *would* prompt.
    monkeypatch.setattr(
        cli_mod, "detect_tool", lambda name: ToolStatus(name=name, state="absent")
    )
    monkeypatch.setattr(cli_mod, "install_command", lambda _name: plan)
    monkeypatch.setattr(cli_mod, "run_install", _spy_install)
    monkeypatch.setattr(
        cli_mod, "detect_auth", lambda tool: AuthStatus(tool=tool, state="logged_in")
    )
    monkeypatch.setattr(cli_mod, "missing_secrets", list)
    monkeypatch.setattr(
        cli_mod,
        "provision_missing",
        lambda **_k: ProvisionResult(provisioned=False, groups=[]),
    )

    # Non-interactive: stdin is not a TTY and a prompt would hit EOF.
    class _ClosedStdin:
        def isatty(self) -> bool:
            return False

    monkeypatch.setattr(cli_mod.sys, "stdin", _ClosedStdin())

    def _eof_input(*_a: object, **_k: object) -> str:
        raise EOFError

    monkeypatch.setattr("builtins.input", _eof_input)

    # AC1: no EOFError / traceback escapes -> a sane (clean) exit, not exit 1.
    with pytest.raises(SystemExit) as exc_info:
        app(["bootstrap"])

    assert exc_info.value.code in (0, None)
    captured = capsys.readouterr()
    # AC2/AC3: nothing is installed without an explicit yes on a non-TTY shell.
    for _args, kwargs in install_calls:
        assert kwargs.get("confirm", False) is not True
    # AC1: the user is told why nothing was installed (clean message, no trace).
    combined = (captured.out + captured.err).lower()
    assert "non-interactive" in combined
    assert "eoferror" not in combined
    assert "traceback" not in combined
