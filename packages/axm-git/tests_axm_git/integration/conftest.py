"""Integration fixtures for git_commit hook-restore invariants.

Provide a real git repo under ``tmp_path`` and a parametrisable
``pre-commit`` hook installer (green / failing / autofix-then-green) so the
scoped-restore behaviour of :class:`axm_git.tools.commit.GitCommitTool` can be
exercised against genuine ``git`` output, zero network, never the CWD repo.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

__all__ = ["commit_repo", "install_hook", "scrubbed_axm_home"]


@pytest.fixture
def scrubbed_axm_home(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> Path:
    """Hermetic ``HOME`` + scrubbed env so config resolves only from tmp state.

    The git-identity resolution reads its config from the ``axm_config`` single
    store (``~/.axm/config.toml``) with ``env > file`` precedence, falling back
    to the legacy ``~/axm/git-profiles.toml``. Left to the ambient environment
    the tests would read machine state (a real ``~/.axm``, a stray ``AXM_GIT_*``
    override, the developer's global git config). This fixture removes every
    such seam so a test's *only* config source is the store it builds under
    ``tmp_path``:

    * ``HOME`` → a fresh empty ``tmp_path`` dir (isolates both the store and the
      legacy file); ``USERPROFILE`` and ``XDG_*`` dropped;
    * global/system git config pointed at an empty file (no committer identity
      or include leaks into subprocess ``git`` calls);
    * every ``AXM_*`` env var dropped — ``axm_config`` resolves ``env > file``,
      so a stray ``AXM_GIT_DEFAULT`` on the runner would shadow the tmp store.

    The env seam *is* the store path: redirecting ``HOME`` points ``~/.axm`` at
    the tmp dir, so ``axm_config.set_(...)`` in the test body writes the store
    the resolution then reads. ``HOME`` is minted via ``tmp_path_factory`` (a
    sibling of any per-test ``tmp_path``) so it never lands *inside* a git repo
    a co-fixture initialised at ``tmp_path`` — which the store's in-repo guard
    (``resolve_safe``) would otherwise refuse.
    """
    home = tmp_path_factory.mktemp("axm_home")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("USERPROFILE", raising=False)
    for var in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME"):
        monkeypatch.delenv(var, raising=False)
    empty_gitconfig = home / ".gitconfig-empty"
    empty_gitconfig.touch()
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(empty_gitconfig))
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", str(empty_gitconfig))
    for name in list(os.environ):
        if name.startswith("AXM_"):
            monkeypatch.delenv(name, raising=False)
    return home


def _run(args: list[str], cwd: Path) -> None:
    subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True)


# Parametrisable pre-commit hook bodies. ``git`` runs the hook from the repo
# root, so bare relative paths resolve against the worktree top-level.
_HOOK_BODIES: dict[str, str] = {
    # Always accepts the commit.
    "green": "#!/bin/sh\nexit 0\n",
    # Definitively refuses every attempt (no auto-fix marker → no retry).
    "failing": "#!/bin/sh\necho 'hook refused the commit' >&2\nexit 1\n",
    # Rewrites the staged file and fails once with the canonical marker, then
    # (guarded by a sentinel) accepts the retried commit.
    "autofix": (
        "#!/bin/sh\n"
        'sentinel="$(git rev-parse --git-dir)/autofix-done"\n'
        'if [ ! -f "$sentinel" ]; then\n'
        '  touch "$sentinel"\n'
        '  printf "\\n" >> fix_me.py\n'
        '  echo "files were modified by this hook" >&2\n'
        "  exit 1\n"
        "fi\n"
        "exit 0\n"
    ),
}


@pytest.fixture
def commit_repo(tmp_path: Path) -> Path:
    """A real git repo under ``tmp_path`` with identity + an initial commit."""
    _run(["git", "init", "-q", "-b", "main"], tmp_path)
    _run(["git", "config", "user.email", "test@example.com"], tmp_path)
    _run(["git", "config", "user.name", "Test"], tmp_path)
    _run(["git", "config", "commit.gpgsign", "false"], tmp_path)
    (tmp_path / "README.md").write_text("init\n")
    _run(["git", "add", "-A"], tmp_path)
    _run(["git", "commit", "-q", "-m", "chore: init"], tmp_path)
    return tmp_path


@pytest.fixture
def install_hook(commit_repo: Path) -> Callable[[str], Path]:
    """Install a parametrisable ``pre-commit`` hook; return the repo path.

    The argument selects a hook body from :data:`_HOOK_BODIES`
    (``"green"``, ``"failing"`` or ``"autofix"``).
    """

    def _install(kind: str) -> Path:
        hook = commit_repo / ".git" / "hooks" / "pre-commit"
        hook.write_text(_HOOK_BODIES[kind])
        hook.chmod(0o755)
        return commit_repo

    return _install
