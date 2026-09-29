"""A confined process writes only where it was allowed, in a filtered environment."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

from axm import sandbox as module
from axm.sandbox import (
    PRIVATE_DIRS,
    SANDBOX_EXEC,
    UNCONFINED,
    bubblewrap_argv,
    confinement,
    darwin_profile,
    private_environment,
    run_confined,
)

pytestmark = pytest.mark.integration

JUDGED = Path("/private/tmp/repo")
_WRITE = (
    "import sys, pathlib\n"
    "try:\n"
    "    pathlib.Path(sys.argv[1]).write_text('x')\n"
    "except OSError as exc:\n"
    "    print(type(exc).__name__)\n"
    "else:\n"
    "    print('written')\n"
)


@pytest.fixture
def writable(tmp_path: Path) -> Path:
    inside = tmp_path / "inside"
    inside.mkdir()
    return inside


def _sandboxed(writable: Path) -> None:
    if confinement([writable]).isolation != "sandbox":
        pytest.skip("no OS sandbox applies here (detect-only)")


def test_a_write_outside_the_writable_dirs_is_denied(
    writable: Path, tmp_path: Path
) -> None:
    _sandboxed(writable)
    outside = tmp_path / "outside.txt"

    run = run_confined(
        [sys.executable, "-c", _WRITE, str(outside)], writable=[writable], cwd=writable
    )

    assert run.isolation == "sandbox"
    assert run.stdout.strip() == "PermissionError"
    assert not outside.exists()


def test_a_write_inside_the_writable_dirs_is_allowed(writable: Path) -> None:
    _sandboxed(writable)
    inside = writable / "inside.txt"

    run = run_confined(
        [sys.executable, "-c", _WRITE, str(inside)], writable=[writable], cwd=writable
    )

    assert run.stdout.strip() == "written"
    assert inside.read_text(encoding="utf-8") == "x"


def test_a_protected_tree_inside_a_writable_dir_stays_read_only(
    writable: Path,
) -> None:
    _sandboxed(writable)
    judged = writable / "judged"
    judged.mkdir()

    run = run_confined(
        [sys.executable, "-c", _WRITE, str(judged / "x.txt")],
        writable=[writable],
        protected=[judged],
        cwd=writable,
    )

    assert run.stdout.strip() == "PermissionError"
    assert not (judged / "x.txt").exists()


def test_the_process_sees_only_the_allow_list_and_the_overrides(
    writable: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FORCE_COLOR", "3")
    monkeypatch.setenv("AXM_SANDBOX_LEAK", "leaked")
    monkeypatch.setenv("LANG", "C.UTF-8")
    show = "import os, json; print(json.dumps(dict(os.environ)))"

    run = run_confined(
        [sys.executable, "-c", show],
        writable=[writable],
        cwd=writable,
        env={"ARENA_FLAG": "on"},
        confined=UNCONFINED,
    )

    seen = json.loads(run.stdout)
    assert run.isolation == "detect-only"
    assert seen["ARENA_FLAG"] == "on"
    assert seen["LANG"] == "C.UTF-8"
    assert "FORCE_COLOR" not in seen
    assert "AXM_SANDBOX_LEAK" not in seen


def test_the_private_environment_lives_under_its_root(tmp_path: Path) -> None:
    env = private_environment(tmp_path / "env")

    assert set(env) == set(PRIVATE_DIRS)
    assert env["HOME"] == str(tmp_path / "env" / "home")
    assert env["TMPDIR"] == env["TMP"] == str(tmp_path / "env" / "tmp")
    assert all(Path(path).is_dir() for path in env.values())


def test_no_sandbox_on_the_platform_is_detect_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(module.sys, "platform", "sunos5")

    assert confinement([tmp_path], [JUDGED]) == UNCONFINED
    assert UNCONFINED.prefix == ()


def test_a_sandbox_that_cannot_apply_here_is_detect_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    refusing = tmp_path / "refusing"
    refusing.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    refusing.chmod(0o755)
    monkeypatch.setattr(module.sys, "platform", "darwin")
    monkeypatch.setattr(module, "SANDBOX_EXEC", str(refusing))

    assert confinement([tmp_path], [JUDGED]) == UNCONFINED


def test_a_probe_that_cannot_start_is_detect_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    not_executable = tmp_path / "not-executable"
    not_executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    monkeypatch.setattr(module.sys, "platform", "darwin")
    monkeypatch.setattr(module, "SANDBOX_EXEC", str(not_executable))

    assert confinement([tmp_path], [JUDGED]) == UNCONFINED


def test_a_sandbox_that_applies_confines_the_run(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    accepting = tmp_path / "accepting"
    accepting.write_text('#!/bin/sh\nshift 2\nexec "$@"\n', encoding="utf-8")
    accepting.chmod(0o755)
    monkeypatch.setattr(module.sys, "platform", "darwin")
    monkeypatch.setattr(module, "SANDBOX_EXEC", str(accepting))

    confined = confinement([tmp_path], [JUDGED])

    assert confined.isolation == "sandbox"
    assert confined.prefix[:2] == (str(accepting), "-p")
    assert confined.prefix[2] == darwin_profile([tmp_path], [JUDGED])
    assert SANDBOX_EXEC == "/usr/bin/sandbox-exec"


def test_on_linux_bubblewrap_confines_the_run_when_installed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    bwrap = tmp_path / "bwrap"
    bwrap.write_text(
        '#!/bin/sh\nwhile [ "$1" != "--" ]; do shift; done\nshift\nexec "$@"\n',
        encoding="utf-8",
    )
    bwrap.chmod(0o755)
    monkeypatch.setattr(module.sys, "platform", "linux")
    monkeypatch.setattr(
        module.shutil, "which", lambda name: str(bwrap) if name == "bwrap" else None
    )

    confined = confinement([tmp_path], [JUDGED])

    assert confined.isolation == "sandbox"
    assert confined.prefix == bubblewrap_argv(str(bwrap), [tmp_path], [JUDGED])


def test_real_bubblewrap_blocks_a_protected_child_inside_a_writable_dir(
    writable: Path,
) -> None:
    if not sys.platform.startswith("linux"):
        pytest.skip("bubblewrap is a Linux sandbox")
    if shutil.which("bwrap") is None:
        pytest.skip("bubblewrap is not installed")
    judged = writable / "judged"
    judged.mkdir()
    confined = confinement([writable], [judged])
    if confined.isolation != "sandbox":
        pytest.skip("bubblewrap cannot create a sandbox on this host")

    outside = writable / "allowed.txt"
    allowed = run_confined(
        [sys.executable, "-c", _WRITE, str(outside)],
        writable=[writable],
        protected=[judged],
        cwd=writable,
        confined=confined,
    )
    blocked = run_confined(
        [sys.executable, "-c", _WRITE, str(judged / "forbidden.txt")],
        writable=[writable],
        protected=[judged],
        cwd=writable,
        confined=confined,
    )

    assert allowed.isolation == blocked.isolation == "sandbox"
    assert allowed.stdout.strip() == "written"
    assert outside.read_text(encoding="utf-8") == "x"
    assert blocked.stdout.strip() == "PermissionError"
    assert not (judged / "forbidden.txt").exists()
