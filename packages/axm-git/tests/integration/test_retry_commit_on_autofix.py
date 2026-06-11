"""Integration: autofix-retry routes through the shared core helper (AC2).

After AXM-1899 the autofix-retry plumbing is a single core helper shared by
both surfaces.  This test exercises it through the lowest public boundary
(``GitCommitTool.execute``): a pre-commit hook that reformats a staged file
makes the first commit fail with the ``files were modified by this hook``
marker; the core retry helper must re-stage the spec files (via the AXM-1898
resolver) and retry the commit once, so the second attempt succeeds.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from axm_git.tools.commit import GitCommitTool

pytestmark = pytest.mark.integration


def _run(cmd: list[str], cwd: Path) -> None:
    subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True)


@pytest.fixture
def workspace_repo(tmp_path: Path) -> tuple[Path, Path]:
    """Init a workspace-style git repo with a ``packages/pkg/`` subdir.

    Returns ``(git_root, package_dir)`` where ``package_dir`` is intended to
    be used as the tool ``path`` (a sub-directory of the git root), so the
    re-stage exercises the subdir-aware resolver.
    """
    _run(["git", "init", "-q", "-b", "main"], tmp_path)
    _run(["git", "config", "user.email", "test@example.com"], tmp_path)
    _run(["git", "config", "user.name", "Test"], tmp_path)
    _run(["git", "config", "commit.gpgsign", "false"], tmp_path)
    pkg_dir = tmp_path / "packages" / "pkg"
    (pkg_dir / "docs").mkdir(parents=True)
    (pkg_dir / "docs" / "foo.md").write_text("initial\n")
    _run(["git", "add", "-A"], tmp_path)
    _run(["git", "commit", "-q", "-m", "init"], tmp_path)
    return tmp_path, pkg_dir


def _install_autofix_hook(git_root: Path) -> None:
    """Install a pre-commit hook that reformats foo.md and fails once.

    The hook strips trailing whitespace from ``packages/pkg/docs/foo.md`` and
    exits 1 with the canonical marker on the first run (guarded by a
    sentinel); once normalised it exits 0, so the retried commit can land.
    """
    hook = git_root / ".git" / "hooks" / "pre-commit"
    hook.write_text(
        "#!/bin/sh\n"
        'sentinel="$(git rev-parse --git-dir)/autofix-done"\n'
        'if [ ! -f "$sentinel" ]; then\n'
        '  touch "$sentinel"\n'
        '  sed -i.bak "s/  *$//" packages/pkg/docs/foo.md\n'
        "  rm -f packages/pkg/docs/foo.md.bak\n"
        '  echo "files were modified by this hook" >&2\n'
        "  exit 1\n"
        "fi\n"
        "exit 0\n"
    )
    hook.chmod(0o755)


def test_autofix_retry_via_shared_core_helper(
    workspace_repo: tuple[Path, Path],
) -> None:
    """AC2: commit fails once on autofix, re-stages via core, then succeeds."""
    git_root, pkg_dir = workspace_repo
    (pkg_dir / "docs" / "foo.md").write_text("autofixed   \n")  # trailing ws
    _install_autofix_hook(git_root)

    result = GitCommitTool().execute(
        path=str(pkg_dir),
        commits=[{"message": "docs: foo", "files": ["packages/pkg/docs/foo.md"]}],
    )

    assert result.success, result.error
    log = subprocess.run(
        ["git", "log", "--oneline"],
        cwd=git_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "docs: foo" in log
