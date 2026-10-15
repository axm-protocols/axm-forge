"""The axm_config pytest11 plugin sandboxes every pytest session by default."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

import pytest

pytest_plugins = ["pytester"]

_OVERRIDES = (
    "AXM_PATHS_SESSIONS_ROOT",
    "AXM_PATHS_QUALITY_DIR",
    "AXM_PATHS_PROTOCOLS_DIR",
    "AXM_PATHS_WARDEN_SOCKET",
    "AXM_TICKETS_DB_PATH",
    "AXM_WARDEN_LOG_PATH",
    "AXM_HOME",
    "AXM_PROFILE",
)

_INNER_DUMP = """
import json
import os
from pathlib import Path

from axm_config import (
    protocols_dir,
    quality_dir,
    sessions_root,
    tickets_db,
    warden_log_path,
    warden_socket,
)
from axm_config.sandbox import active_sandbox


def test_dump():
    sandbox = active_sandbox()
    root = None if sandbox is None else sandbox.root
    resolvers = {
        "sessions_root": sessions_root,
        "quality_dir": quality_dir,
        "protocols_dir": protocols_dir,
        "tickets_db": tickets_db,
        "warden_socket": warden_socket,
        "warden_log_path": warden_log_path,
    }
    report = {
        "root": None if root is None else str(root),
        "root_is_dir": root is not None and root.is_dir(),
        "paths": {name: str(fn()) for name, fn in resolvers.items()},
        "home_env": os.environ.get("HOME"),
        "path_home": str(Path.home()),
    }
    Path(__file__).with_name("report.json").write_text(json.dumps(report))
"""

_INNER_MARKER = """
from pathlib import Path


def test_marker():
    Path(__file__).with_name("marker.txt").write_text("ran")
"""


@pytest.fixture
def clean_launch(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    """Launch environment with none of the override variables set."""
    for name in _OVERRIDES:
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


def _launch_home() -> Path:
    return Path(os.environ["HOME"])


def _under(path: Path, base: Path) -> bool:
    return path.resolve().is_relative_to(base.resolve())


def _run_dump(pytester: pytest.Pytester) -> dict[str, Any]:
    report_file = pytester.path / "report.json"
    if report_file.exists():
        report_file.unlink()
    pytester.makepyfile(test_inner_dump=_INNER_DUMP)
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)
    report: dict[str, Any] = json.loads(report_file.read_text())
    return report


@pytest.mark.integration
@pytest.mark.parametrize("profile", [None, "production", "dev"])
def test_six_state_paths_isolated_by_default(
    pytester: pytest.Pytester,
    clean_launch: pytest.MonkeyPatch,
    profile: str | None,
) -> None:
    """AC1: every state path lies under a temp sandbox root; HOME is untouched."""
    if profile is not None:
        clean_launch.setenv("AXM_PROFILE", profile)
    home = _launch_home()
    path_home = Path.home()

    report = _run_dump(pytester)

    assert report["root"] is not None
    root = Path(report["root"])
    assert _under(root, Path(tempfile.gettempdir()))
    assert set(report["paths"]) == {
        "sessions_root",
        "quality_dir",
        "protocols_dir",
        "tickets_db",
        "warden_socket",
        "warden_log_path",
    }
    for raw in report["paths"].values():
        path = Path(raw)
        assert path.is_relative_to(root), raw
        assert not _under(path, home / "axm"), raw
        assert not _under(path, home / ".axm"), raw
    sessions = Path(report["paths"]["sessions_root"])
    assert not _under(sessions, home / ".axm" / "profiles" / "dev")
    assert report["home_env"] == str(home)
    assert report["path_home"] == str(path_home)


@pytest.mark.integration
def test_two_sessions_get_two_roots(
    pytester: pytest.Pytester, clean_launch: pytest.MonkeyPatch
) -> None:
    """AC2: two consecutive sessions report two different sandbox roots."""
    first = _run_dump(pytester)["root"]
    second = _run_dump(pytester)["root"]

    assert first is not None
    assert second is not None
    assert first != second


@pytest.mark.integration
@pytest.mark.parametrize(
    ("variable", "relative"),
    [
        ("AXM_TICKETS_DB_PATH", "axm/tickets/tickets.db"),
        ("AXM_PATHS_SESSIONS_ROOT", ".axm/sessions-leak"),
    ],
)
def test_escaping_launch_variable_aborts_before_any_test(
    pytester: pytest.Pytester,
    clean_launch: pytest.MonkeyPatch,
    variable: str,
    relative: str,
) -> None:
    """AC3: a launch variable aimed at real AXM state aborts the session."""
    clean_launch.setenv(variable, str(_launch_home() / relative))
    pytester.makepyfile(test_inner_marker=_INNER_MARKER)

    result = pytester.runpytest()

    assert result.ret != 0
    assert not (pytester.path / "marker.txt").exists()
    assert variable in result.stdout.str() + result.stderr.str()


@pytest.mark.integration
def test_launch_axm_home_config_db_path_does_not_reach_tests(
    pytester: pytest.Pytester, clean_launch: pytest.MonkeyPatch
) -> None:
    """AC4: a launch AXM_HOME config.toml db_path never reaches tickets_db()."""
    home = _launch_home()
    axm_home = pytester.mkdir("launch-axm-home")
    production_db = home / "axm" / "tickets" / "tickets.db"
    (axm_home / "config.toml").write_text(f'[tickets]\ndb_path = "{production_db}"\n')
    clean_launch.setenv("AXM_HOME", str(axm_home))

    report = _run_dump(pytester)

    assert report["root"] is not None
    tickets = Path(report["paths"]["tickets_db"])
    assert tickets.is_relative_to(Path(report["root"]))
    assert not _under(tickets, home / "axm")
    assert not _under(tickets, home / ".axm")


@pytest.mark.integration
def test_socket_under_sandbox_within_af_unix_limit(
    pytester: pytest.Pytester, clean_launch: pytest.MonkeyPatch
) -> None:
    """AC5: warden_socket() lies under the sandbox root and fits AF_UNIX."""
    report = _run_dump(pytester)

    assert report["root"] is not None
    socket = Path(report["paths"]["warden_socket"])
    assert socket.is_relative_to(Path(report["root"]))
    assert len(os.fsencode(socket)) < 104


@pytest.mark.integration
def test_root_exists_during_session_and_is_removed_after(
    pytester: pytest.Pytester, clean_launch: pytest.MonkeyPatch
) -> None:
    """AC6: the root exists outside HOME during the session, gone after it."""
    home = _launch_home()

    report = _run_dump(pytester)

    assert report["root"] is not None
    root = Path(report["root"])
    assert report["root_is_dir"] is True
    assert not _under(root, home)
    assert root.exists() is False
