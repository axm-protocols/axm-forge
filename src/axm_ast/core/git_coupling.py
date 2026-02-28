"""Git change coupling — files that historically co-change.

Analyzes ``git log`` to find files that change together, revealing
hidden dependencies invisible to static analysis.

The coupling formula follows Axon's approach::

    coupling(A, B) = co_changes(A, B) / max(changes(A), changes(B))

Example:
    >>> from axm_ast.core.git_coupling import git_coupled_files
    >>> git_coupled_files("src/core.py", Path("/project"), months=6)
    [{"file": "src/utils.py", "strength": 0.75, "co_changes": 6}]
"""

from __future__ import annotations

import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

__all__ = ["git_coupled_files"]

# Binary / non-source extensions to filter out from coupling results.
_BINARY_EXTENSIONS = frozenset(
    {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".bmp",
        ".ico",
        ".svg",
        ".webp",
        ".mp3",
        ".mp4",
        ".wav",
        ".ogg",
        ".zip",
        ".tar",
        ".gz",
        ".bz2",
        ".pdf",
        ".woff",
        ".woff2",
        ".ttf",
        ".eot",
        ".pyc",
        ".pyo",
        ".so",
        ".dll",
        ".exe",
        ".o",
        ".a",
        ".lib",
        ".db",
        ".sqlite",
    }
)


def _is_binary(file_path: str) -> bool:
    """Check if a file path looks like a binary file."""
    return Path(file_path).suffix.lower() in _BINARY_EXTENSIONS


def _parse_git_log(project_root: Path, months: int) -> list[set[str]]:
    """Parse git log into a list of file-sets per commit.

    Args:
        project_root: Root of the git repository.
        months: Number of months of history to analyze.

    Returns:
        List of sets, each containing the files changed in one commit.
    """
    try:
        result = subprocess.run(
            [
                "git",
                "log",
                "--name-only",
                f"--since={months}.months",
                "--format=%H",
                "--no-merges",
            ],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        # git not installed
        return []

    if result.returncode != 0:
        return []

    commits: list[set[str]] = []
    current_files: set[str] = set()

    for line in result.stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        # Commit hashes are 40 hex chars
        if len(stripped) == 40 and all(c in "0123456789abcdef" for c in stripped):
            if current_files:
                commits.append(current_files)
            current_files = set()
        else:
            # Filter binary files
            if not _is_binary(stripped):
                current_files.add(stripped)

    # Don't forget the last commit
    if current_files:
        commits.append(current_files)

    return commits


def git_coupled_files(
    file_path: str | Path,
    project_root: Path,
    *,
    months: int = 6,
    min_strength: float = 0.3,
    min_co_changes: int = 3,
) -> list[dict[str, Any]]:
    """Find files that historically co-change with the target file.

    Analyzes ``git log`` over ``months`` of history to compute
    change coupling strength for each file that co-occurs with
    *file_path* in commits.

    Args:
        file_path: Relative path to the target file within the repo.
        project_root: Root of the git repository.
        months: Number of months of history to analyze.
        min_strength: Minimum coupling strength (0.0-1.0).
        min_co_changes: Minimum number of co-changes required.

    Returns:
        List of dicts with ``file``, ``strength``, ``co_changes``,
        sorted by strength descending.  Returns empty list if not
        in a git repo or on error.

    Example:
        >>> result = git_coupled_files("src/core.py", Path("."))
        >>> result[0]["file"]
        'src/utils.py'
    """
    target = str(file_path)
    commits = _parse_git_log(project_root, months)
    if not commits:
        return []

    # Count how many commits each file appears in
    file_changes: Counter[str] = Counter()
    # Count how many commits contain both target and another file
    co_changes: Counter[str] = Counter()

    for file_set in commits:
        for f in file_set:
            file_changes[f] += 1
        if target in file_set:
            for f in file_set:
                if f != target:
                    co_changes[f] += 1

    target_changes = file_changes.get(target, 0)
    if target_changes == 0:
        return []

    # Compute coupling strength
    coupled: list[dict[str, Any]] = []
    for other_file, co_count in co_changes.items():
        other_changes = file_changes[other_file]
        strength = co_count / max(target_changes, other_changes)

        if strength >= min_strength and co_count >= min_co_changes:
            coupled.append(
                {
                    "file": other_file,
                    "strength": round(strength, 4),
                    "co_changes": co_count,
                }
            )

    # Sort by strength descending
    coupled.sort(key=lambda x: x["strength"], reverse=True)
    return coupled
