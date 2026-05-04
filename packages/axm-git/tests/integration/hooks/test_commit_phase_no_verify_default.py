"""AXM-1645 integration tests: real git repo + real pre-commit hooks.

Verifies that with ``skip_hooks=False`` (new default) project hooks run,
and with ``skip_hooks=True`` they are bypassed. Also covers the autofix
retry path under the new default.
"""

from __future__ import annotations

import stat
import subprocess
from pathlib import Path

import pytest

from axm_git.hooks.commit_phase import CommitPhaseHook

pytestmark = pytest.mark.integration


def _init_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.test"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=path, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=path, check=True)


def _write_hook(repo: Path, script: str) -> Path:
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.write_text(script)
    hook.chmod(hook.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return hook


def _make_file(repo: Path, name: str = "a.txt", content: str = "hello\n") -> str:
    (repo / name).write_text(content)
    return name


def _spec(files: list[str], message: str = "test commit") -> dict:
    return {"message": message, "files": files}


def test_commit_phase_runs_pre_commit_hook_by_default(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _write_hook(tmp_path, "#!/bin/sh\necho 'hook says no' >&2\nexit 1\n")
    fname = _make_file(tmp_path)

    hook = CommitPhaseHook()
    ctx = {"phase_name": "build", "commit_spec": _spec([fname])}
    result = hook.execute(ctx, from_outputs=True, working_dir=str(tmp_path))

    assert result.success is False
    assert "hook says no" in (result.error or "") or "git commit failed" in (
        result.error or ""
    )


def test_commit_phase_skip_hooks_true_bypasses(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _write_hook(tmp_path, "#!/bin/sh\nexit 1\n")
    fname = _make_file(tmp_path)

    hook = CommitPhaseHook()
    ctx = {"phase_name": "build", "commit_spec": _spec([fname])}
    result = hook.execute(
        ctx, from_outputs=True, working_dir=str(tmp_path), skip_hooks=True
    )

    assert result.success is True


def test_commit_phase_autofix_retry_under_new_default(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    flag = tmp_path / ".hook_ran"
    fname = _make_file(tmp_path, content="original\n")
    _write_hook(
        tmp_path,
        f"""#!/bin/sh
if [ ! -f "{flag}" ]; then
  touch "{flag}"
  echo "rewriting" > "{tmp_path / fname}"
  echo "files were modified" >&2
  exit 1
fi
exit 0
""",
    )

    hook = CommitPhaseHook()
    ctx = {"phase_name": "build", "commit_spec": _spec([fname])}
    result = hook.execute(ctx, from_outputs=True, working_dir=str(tmp_path))

    assert result.success is True
    assert flag.exists()


def test_commit_phase_pre_commit_failure_routes_to_fail(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _write_hook(
        tmp_path,
        "#!/bin/sh\necho 'lint error: bad style' >&2\nexit 1\n",
    )
    fname = _make_file(tmp_path)

    hook = CommitPhaseHook()
    ctx = {"phase_name": "build", "commit_spec": _spec([fname])}
    result = hook.execute(ctx, from_outputs=True, working_dir=str(tmp_path))

    assert result.success is False
    assert "lint error" in (result.error or "")
    # Ensure no commit was created
    log = subprocess.run(
        ["git", "log", "--oneline"], cwd=tmp_path, capture_output=True, text=True
    )
    assert log.stdout.strip() == ""
