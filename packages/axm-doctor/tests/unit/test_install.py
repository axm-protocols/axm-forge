from __future__ import annotations

import re
from typing import Literal

from pytest_mock import MockerFixture

from axm_doctor.detect import ToolStatus
from axm_doctor.install import (
    _MAX_SCRIPT_BYTES,
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


def test_registry_exposes_gh_proposal() -> None:
    """AC1: gh has a registered plan with its official documented command."""
    plan = install_command("gh")
    assert isinstance(plan, InstallPlan)
    assert plan.tool == "gh"
    # gh's official macOS install command is `brew install gh`.
    assert plan.human_command == "brew install gh"
    assert plan.argv == ["brew", "install", "gh"]


def test_registry_omits_system_prerequisites() -> None:
    """AC3: git/node/npm are out-of-scope prerequisites with no proposed plan."""
    for prerequisite in ("git", "node", "npm"):
        assert install_command(prerequisite) is None


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


class _FakeOKResponse:
    """A 200 response whose ``read(amt)`` honours the bounded-read cap."""

    status = 200

    def __init__(self, body: bytes) -> None:
        self._body = body

    def read(self, amt: int | None = None) -> bytes:
        return self._body if amt is None else self._body[:amt]

    def __enter__(self) -> _FakeOKResponse:
        return self

    def __exit__(self, *_exc: object) -> Literal[False]:
        return False


def test_uv_fetch_url_is_pinned_versioned() -> None:
    """AC1: the uv plan's fetch_url is a pinned, versioned endpoint."""
    plan = install_command("uv")
    assert plan is not None
    assert plan.fetch_url is not None
    # A pinned URL carries a version segment (``/uv/<version>/install.sh``),
    # NOT the floating ``/uv/install.sh`` latest endpoint.
    assert plan.fetch_url != "https://astral.sh/uv/install.sh"
    assert re.search(r"astral\.sh/uv/\d[\w.\-]*/install\.sh$", plan.fetch_url)


def test_fetch_install_non_https_rejected_before_exec(
    mocker: MockerFixture,
) -> None:
    """AC2: a non-HTTPS fetch_url is refused before any network call or exec."""
    open_spy = mocker.patch("axm_doctor.install.urllib.request.urlopen")
    run_spy = mocker.patch("axm_doctor.install.subprocess.run")
    mocker.patch(
        "axm_doctor.install.detect_tool",
        return_value=ToolStatus(name="uv", state="absent"),
    )

    plan = InstallPlan(
        tool="uv",
        argv=["curl", "-LsSf", "http://astral.sh/uv/0.8.4/install.sh"],
        human_command="curl -LsSf http://astral.sh/uv/0.8.4/install.sh | sh",
        fetch_url="http://astral.sh/uv/0.8.4/install.sh",  # non-HTTPS
    )

    result = run_install(plan, confirm=True)

    assert result.returncode is not None
    assert result.returncode != 0
    open_spy.assert_not_called()  # rejected before the fetch
    run_spy.assert_not_called()  # sh <tmpfile> never ran


def test_fetch_install_oversize_body_rejected_before_exec(
    mocker: MockerFixture,
) -> None:
    """AC2: a body over the size cap is refused, never written or executed."""
    oversize = b"a" * (_MAX_SCRIPT_BYTES + 10)
    mocker.patch(
        "axm_doctor.install.urllib.request.urlopen",
        return_value=_FakeOKResponse(oversize),
    )
    run_spy = mocker.patch("axm_doctor.install.subprocess.run")
    mocker.patch(
        "axm_doctor.install.detect_tool",
        return_value=ToolStatus(name="uv", state="absent"),
    )

    plan = install_command("uv")
    assert plan is not None
    assert plan.fetch_url is not None

    result = run_install(plan, confirm=True)

    assert result.returncode is not None
    assert result.returncode != 0
    run_spy.assert_not_called()  # oversize script never executed


def test_fetch_install_wellformed_body_accepted(mocker: MockerFixture) -> None:
    """AC1: a small HTTPS 200 body is written and the sh <tmpfile> step runs."""
    mocker.patch(
        "axm_doctor.install.urllib.request.urlopen",
        return_value=_FakeOKResponse(b"#!/bin/sh\necho installing uv\n"),
    )
    run_spy = mocker.patch(
        "axm_doctor.install.subprocess.run",
        return_value=mocker.Mock(returncode=0),
    )
    mocker.patch(
        "axm_doctor.install.detect_tool",
        return_value=ToolStatus(name="uv", state="present"),
    )

    plan = install_command("uv")
    assert plan is not None

    result = run_install(plan, confirm=True)

    assert result.executed is True
    assert result.returncode == 0
    run_spy.assert_called_once()  # sh <tmpfile> install step invoked
