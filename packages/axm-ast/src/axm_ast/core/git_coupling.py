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

import logging
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["git_coupled_files"]

_COMMIT_HASH_LEN = 40

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


def _run_git_log(project_root: Path, months: int) -> str | None:
    """Run ``git log`` and return stdout, or *None* on failure."""
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
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def _is_commit_hash(s: str) -> bool:
    """Check whether *s* looks like a 40-char hex commit hash."""
    return len(s) == _COMMIT_HASH_LEN and all(c in "0123456789abcdef" for c in s)


def _parse_git_log(project_root: Path, months: int) -> list[set[str]]:
    """Parse git log into a list of file-sets per commit.

    Args:
        project_root: Root of the git repository.
        months: Number of months of history to analyze.

    Returns:
        List of sets, each containing the files changed in one commit.
    """
    stdout = _run_git_log(project_root, months)
    if stdout is None:
        return []

    commits: list[set[str]] = []
    current_files: set[str] = set()

    for line in stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if _is_commit_hash(stripped):
            if current_files:
                commits.append(current_files)
            current_files = set()
        elif not _is_binary(stripped):
            current_files.add(stripped)

    if current_files:
        commits.append(current_files)

    return commits


def _count_co_changes(
    target: str,
    commits: list[set[str]],
) -> tuple[Counter[str], Counter[str]]:
    """Return (file_changes, co_changes) counters for *target*."""
    file_changes: Counter[str] = Counter()
    co_changes: Counter[str] = Counter()
    for file_set in commits:
        for f in file_set:
            file_changes[f] += 1
        if target in file_set:
            for f in file_set:
                if f != target:
                    co_changes[f] += 1
    return file_changes, co_changes


def _compute_coupling_scores(
    target: str,
    commits: list[set[str]],
    *,
    min_strength: float,
    min_co_changes: int,
) -> list[dict[str, Any]]:
    """Compute coupling strength between *target* and all co-changed files."""
    file_changes, co_changes = _count_co_changes(target, commits)

    target_changes = file_changes.get(target, 0)
    if target_changes == 0:
        return []

    coupled: list[dict[str, Any]] = []
    for other_file, co_count in co_changes.items():
        strength = co_count / max(target_changes, file_changes[other_file])
        if strength >= min_strength and co_count >= min_co_changes:
            coupled.append(
                {
                    "file": other_file,
                    "strength": round(strength, 4),
                    "co_changes": co_count,
                }
            )

    coupled.sort(key=lambda x: x["strength"], reverse=True)
    return coupled


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
        ```python
        >>> result = git_coupled_files("src/core.py", Path("."))
        >>> result[0]["file"]
        'src/utils.py'
        ```
    """
    commits = _parse_git_log(project_root, months)
    if not commits:
        return []

    return _compute_coupling_scores(
        str(file_path),
        commits,
        min_strength=min_strength,
        min_co_changes=min_co_changes,
    )
