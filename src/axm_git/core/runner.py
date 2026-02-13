"""Subprocess runners for git, gh, and uv commands."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

__all__ = ["detect_package_name", "gh_available", "run_gh", "run_git"]


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
    except Exception:
        return None
