"""Read-only commit-range measurements and disposable revision exports."""

from __future__ import annotations

import io
import re
import subprocess
import tarfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from axm_git.core.runner import run_git

__all__ = ["ChangedFile", "Hunk", "export_revision", "range_diff", "resolve_revision"]


@dataclass(frozen=True)
class Hunk:
    """Line intervals on both sides; zero count denotes an insertion/deletion."""

    old_start: int
    old_count: int
    new_start: int
    new_count: int


@dataclass(frozen=True)
class ChangedFile:
    """A repository-relative file and its changed line intervals."""

    path: str
    hunks: tuple[Hunk, ...]


def _output(root: Path, args: list[str]) -> str:
    result = run_git(args, root)
    if result.returncode:
        raise ValueError(result.stderr.strip())
    return result.stdout


def resolve_revision(root: Path, rev: str) -> str:
    """Resolve a non-option commit ref once before measuring or exporting it."""
    if not rev or rev.startswith("-"):
        raise ValueError("a non-option commit revision is required")
    return _output(root, ["rev-parse", "--verify", rev + "^{commit}"]).strip()


def range_diff(root: Path, base: str, head: str) -> tuple[ChangedFile, ...]:
    """Measure a pinned base..head range, independent of index/worktree state."""
    base, head = resolve_revision(root, base), resolve_revision(root, head)
    names = _output(
        root,
        [
            "diff",
            "--no-ext-diff",
            "--no-renames",
            "--name-only",
            "-z",
            base,
            head,
            "--",
        ],
    )
    rows: list[ChangedFile] = []
    pattern = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
    for name in sorted(filter(None, names.split("\0"))):
        patch = _output(
            root,
            [
                "diff",
                "--no-ext-diff",
                "--no-textconv",
                "--no-renames",
                "--unified=0",
                base,
                head,
                "--",
                name,
            ],
        )
        hunks = []
        for line in patch.splitlines():
            match = pattern.match(line)
            if match:
                a, b, c, d = match.groups()
                hunks.append(Hunk(int(a), int(b or 1), int(c), int(d or 1)))
        rows.append(ChangedFile(name, tuple(hunks)))
    return tuple(rows)


@contextmanager
def export_revision(root: Path, rev: str) -> Iterator[Path]:
    """Export tracked regular files to a temporary tree without registering worktrees.

    Symlinks and submodules are not followed. No files or refs in the source
    repository are modified. The export contains no executable git history.
    """
    sha = resolve_revision(root, rev)
    result = subprocess.run(
        ["git", "archive", "--format=tar", sha],
        cwd=root,
        capture_output=True,
        check=False,
        timeout=120,
    )
    if result.returncode:
        raise ValueError(result.stderr.decode(errors="replace"))
    with TemporaryDirectory(prefix="axm-revision-") as directory:
        dest = Path(directory).resolve()
        with tarfile.open(fileobj=io.BytesIO(result.stdout)) as archive:
            members = [
                member for member in archive if member.isfile() or member.isdir()
            ]
            archive.extractall(dest, members=members, filter="data")
        yield dest
