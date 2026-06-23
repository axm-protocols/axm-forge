from __future__ import annotations

from typing import Literal

from pytest_mock import MockerFixture

from axm_doctor.detect import ToolStatus
from axm_doctor.install import (
    InstallPlan,
    InstallResult,
    install_command,
    run_install,
)


def test_install_command_known_tool() -> None:
    """AC1: install_command(known) returns the official install argv/plan."""
    plan = install_command("uv")
    assert isinstance(plan, InstallPlan)
    assert plan.tool == "uv"
    # The uv installer pulls the script from astral.sh.
    assert "astral.sh" in plan.human_command
    assert any("astral.sh" in part for part in plan.argv)


def test_install_command_npm_tools() -> None:
    """AC1: claude/codex resolve to their official npm install argv."""
    claude = install_command("claude")
    assert claude is not None
    assert claude.argv == ["npm", "i", "-g", "@anthropic-ai/claude-code"]

    codex = install_command("codex")
    assert codex is not None
    assert codex.argv == ["npm", "i", "-g", "@openai/codex"]


def test_install_command_unknown_returns_none() -> None:
    """AC2: an unknown tool returns None rather than guessing a command."""
    assert install_command("bogus") is None


def test_run_install_dry_run_does_not_execute(mocker: MockerFixture) -> None:
    """AC3, AC5: confirm=False is a dry-run: subprocess NOT called, command echoed."""
    spy = mocker.patch("axm_doctor.install.subprocess.run")
    plan = install_command("claude")
    assert plan is not None
    result = run_install(plan, confirm=False)
    assert isinstance(result, InstallResult)
    spy.assert_not_called()
    assert result.executed is False
    assert result.returncode is None
    # The command it WOULD run is echoed back to the caller.
    assert plan.human_command in result.command


def test_run_install_confirm_executes(mocker: MockerFixture) -> None:
    """AC3: confirm=True executes the command exactly once."""
    from axm_doctor.detect import ToolStatus

    fake = mocker.Mock(returncode=0)
    spy = mocker.patch("axm_doctor.install.subprocess.run", return_value=fake)
    # Stub the post-install re-detect so the spy counts only the install call.
    mocker.patch(
        "axm_doctor.install.detect_tool",
        return_value=ToolStatus(name="claude", state="present"),
    )
    plan = install_command("claude")
    assert plan is not None
    result = run_install(plan, confirm=True)
    spy.assert_called_once()
    assert result.executed is True
    assert result.returncode == 0


def test_confirm_defaults_false(mocker: MockerFixture) -> None:
    """AC5: the default path NEVER installs silently — confirm defaults to False."""
    spy = mocker.patch("axm_doctor.install.subprocess.run")
    plan = install_command("uv")
    assert plan is not None
    result = run_install(plan)  # no confirm kwarg
    spy.assert_not_called()
    assert result.executed is False


def test_run_install_confirm_post_detects_tool(mocker: MockerFixture) -> None:
    """AC4: after a real install, run_install re-detects the tool via detect_tool."""
    from axm_doctor.detect import ToolStatus

    mocker.patch(
        "axm_doctor.install.subprocess.run", return_value=mocker.Mock(returncode=0)
    )
    detect = mocker.patch(
        "axm_doctor.install.detect_tool",
        return_value=ToolStatus(
            name="claude", state="present", version="1.0", path="/usr/bin/claude"
        ),
    )
    plan = install_command("claude")
    assert plan is not None
    result = run_install(plan, confirm=True)
    detect.assert_called_once_with("claude")
    assert result.post_check is not None
    assert result.post_check.state == "present"


def test_run_install_dry_run_skips_post_detect(mocker: MockerFixture) -> None:
    """AC4, AC5: a dry-run does not re-detect (nothing was installed)."""
    detect = mocker.patch("axm_doctor.install.detect_tool")
    plan = install_command("uv")
    assert plan is not None
    result = run_install(plan, confirm=False)
    detect.assert_not_called()
    assert result.post_check is None


def test_fetch_install_non_200_fails_safely(mocker: MockerFixture) -> None:
    """AC1: a non-200 HTTP response is NOT piped to sh; result is failed.

    The uv installer is fetched over HTTPS. If the server answers 503 (or any
    non-200), the body is an error page, not an installer script: it must never
    be written to a temp file and executed via ``sh <tmpfile>``. run_install
    must return a failed InstallResult and the subprocess must never fire.
    """

    class _FakeResponse:
        status = 503

        def read(self) -> bytes:
            return b"<html>503 Service Unavailable</html>"

        def __enter__(self) -> _FakeResponse:
            return self

        def __exit__(self, *_exc: object) -> Literal[False]:
            return False

    mocker.patch(
        "axm_doctor.install.urllib.request.urlopen",
        return_value=_FakeResponse(),
    )
    # The sh <tmpfile> exec must NEVER happen for a non-200 response.
    run_spy = mocker.patch("axm_doctor.install.subprocess.run")
    mocker.patch(
        "axm_doctor.install.detect_tool",
        return_value=ToolStatus(name="uv", state="absent"),
    )

    plan = install_command("uv")
    assert plan is not None
    assert plan.fetch_url is not None  # script-installer path

    result = run_install(plan, confirm=True)

    assert isinstance(result, InstallResult)
    assert result.returncode is not None
    assert result.returncode != 0  # failed: error page was not executed
    run_spy.assert_not_called()  # sh <tmpfile> never ran on a 503


def test_run_argv_missing_binary_clean(mocker: MockerFixture) -> None:
    """AC4: an install argv pointing at a missing binary yields a clean result.

    A FileNotFoundError/OSError from the subprocess must be caught and turned
    into a failed InstallResult, never an uncaught traceback.
    """
    mocker.patch(
        "axm_doctor.install.subprocess.run",
        side_effect=FileNotFoundError(2, "No such file or directory", "npm"),
    )
    mocker.patch(
        "axm_doctor.install.detect_tool",
        return_value=ToolStatus(name="claude", state="absent"),
    )

    plan = install_command("claude")  # plain argv plan (npm i -g ...)
    assert plan is not None
    assert plan.fetch_url is None

    result = run_install(plan, confirm=True)

    assert isinstance(result, InstallResult)
    assert result.executed is True
    assert result.returncode is not None
    assert result.returncode != 0
