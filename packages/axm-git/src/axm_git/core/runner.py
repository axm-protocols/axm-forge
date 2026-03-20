"""Subprocess runners for git, gh, and uv commands."""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path
from typing import Any

from axm.tools.base import ToolResult

logger = logging.getLogger(__name__)

__all__ = [
    "detect_package_name",
    "find_git_root",
    "gh_available",
    "not_a_repo_error",
    "run_gh",
    "run_git",
    "suggest_git_repos",
]


def find_git_root(path: Path) -> Path | None:
    """Find the git repository root containing *path*.

    Uses ``git rev-parse --show-toplevel`` which walks up the directory
    tree, supporting mono-repo and workspace layouts where ``.git``
    lives above the package directory.

    Args:
        path: Any directory that may be inside a git repository.

    Returns:
        Repository root as a ``Path``, or ``None`` if *path* is not
        inside a git repository.
    """
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return Path(result.stdout.strip())


def run_git(
    args: list[str],
    cwd: Path,
    **kwargs: Any,
) -> subprocess.CompletedProcess[str]:
    """Run a git command in the given directory.

    Args:
        args: Git subcommand and arguments (e.g. ``["status", "--short"]``).
        cwd: Working directory (project root).
        **kwargs: Extra arguments forwarded to ``subprocess.run``.

    Returns:
        Completed process result.
    """
    kwargs.setdefault("capture_output", True)
    kwargs.setdefault("text", True)
    kwargs.setdefault("check", False)
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        **kwargs,
    )


def gh_available() -> bool:
    """Check whether the GitHub CLI is installed and authenticated."""
    if not shutil.which("gh"):
        return False
    result = subprocess.run(
        ["gh", "auth", "status"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def run_gh(
    args: list[str],
    cwd: Path,
    **kwargs: Any,
) -> subprocess.CompletedProcess[str]:
    """Run a GitHub CLI command.

    Args:
        args: gh subcommand and arguments.
        cwd: Working directory (project root).
        **kwargs: Extra arguments forwarded to ``subprocess.run``.

    Returns:
        Completed process result.

    Raises:
        FileNotFoundError: If ``gh`` is not installed.
    """
    kwargs.setdefault("capture_output", True)
    kwargs.setdefault("text", True)
    kwargs.setdefault("check", False)
    return subprocess.run(
        ["gh", *args],
        cwd=str(cwd),
        **kwargs,
    )


def detect_package_name(project_path: Path) -> str | None:
    """Read the package name from ``pyproject.toml``.

    Args:
        project_path: Project root containing ``pyproject.toml``.

    Returns:
        Package name or ``None`` if not found.
    """
    pyproject = project_path / "pyproject.toml"
    if not pyproject.exists():
        return None

    try:
        import tomllib

        with open(pyproject, "rb") as f:
            data = tomllib.load(f)
        return data.get("project", {}).get("name")  # type: ignore[no-any-return]
    except (OSError, KeyError, ValueError):
        return None


def suggest_git_repos(path: Path) -> list[str]:
    """Find immediate child directories that are git repositories.

    Scans one level deep for subdirectories containing a ``.git`` dir.
    Returns a sorted list of directory names.  If *path* is itself a
    git repository (has ``.git/`` at root), returns an empty list.

    Args:
        path: Directory to scan.

    Returns:
        Sorted list of child directory names that are git repos.
    """
    if (path / ".git").is_dir():
        return []

    repos: list[str] = []
    try:
        children = sorted(path.iterdir())
    except (PermissionError, FileNotFoundError):
        return []

    for child in children:
        if not child.is_dir():
            continue
        try:
            if (child / ".git").is_dir():
                repos.append(child.name)
        except PermissionError:
            continue

    return repos


def not_a_repo_error(stderr: str, path: Path) -> ToolResult:
    """Build a ``ToolResult`` for a failed git command.

    If *stderr* contains ``"not a git repository"`` and *path* has
    child directories that are git repos, the error message is enriched
    with suggestions.  Otherwise a standard error is returned.

    Args:
        stderr: Stderr output from the failed git command.
        path: Directory that was used as ``cwd``.

    Returns:
        ``ToolResult(success=False, ...)`` with optional suggestions.
    """
    msg = stderr.strip()

    if "not a git repository" not in msg:
        return ToolResult(success=False, error=msg)

    suggestions = suggest_git_repos(path)
    if suggestions:
        hint = ", ".join(suggestions)
        return ToolResult(
            success=False,
            error=(
                f"{msg}. This directory contains git repos: {hint}. "
                f"Pass one of these as the path instead."
            ),
            data={"suggestions": suggestions},
        )

    return ToolResult(success=False, error=msg)
