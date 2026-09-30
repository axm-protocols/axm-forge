"""Resolved validation environments for detached git worktrees.

Reuse the source checkout's installed dependencies without uv synchronization.
Candidate src trees precede editable installs in a per-subprocess environment.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

__all__ = ["ValidationEnvironment", "worktree_environment"]


@dataclass(frozen=True)
class ValidationEnvironment:
    """An immutable command/environment pair scoped to one candidate tree."""

    checkout: Path
    source: Path
    venv: Path

    def command(self, command: list[str]) -> list[str]:
        """Run Python instruments in the resolved source environment."""
        python = self.venv / "bin" / "python"
        if not python.is_file():
            raise ValueError(f"validation interpreter missing: {python}")
        if command and command[0] in {"pytest", "ruff", "mypy"}:
            return [str(python), "-m", *command]
        executable = self.venv / "bin" / command[0]
        return [str(executable), *command[1:]] if executable.is_file() else command

    def variables(self) -> dict[str, str]:
        """Overlay candidate modules without changing shared process state."""
        sources = [self.checkout / "src"]
        sources.extend(sorted((self.checkout / "packages").glob("*/src")))
        overlay = [str(path) for path in sources if path.is_dir()]
        env = dict(os.environ)
        previous = env.get("PYTHONPATH")
        env["PYTHONPATH"] = os.pathsep.join(
            [*overlay, *([previous] if previous else [])]
        )
        env["PATH"] = str(self.venv / "bin") + os.pathsep + env.get("PATH", "")
        env["VIRTUAL_ENV"] = str(self.venv)
        return env


def _worktree_source(checkout: Path) -> Path | None:
    marker = checkout / ".git"
    if not marker.is_file():
        return None
    text = marker.read_text().strip()
    if not text.startswith("gitdir: "):
        return None
    gitdir = (checkout / text.removeprefix("gitdir: ")).resolve()
    common = gitdir / "commondir"
    if not common.is_file():
        return None
    common_dir = (gitdir / common.read_text().strip()).resolve()
    # Standard non-bare checkout; refuse to guess for bare/custom layouts.
    if common_dir.name != ".git":
        raise ValueError(f"validation source checkout cannot be located: {common_dir}")
    return common_dir.parent


def worktree_environment(project: Path) -> ValidationEnvironment | None:
    """Find a worktree's source environment; ordinary projects retain their runner.

    Missing source environments fail closed. Falling back to uv in that case would
    resolve path dependencies from the lane and recreate the measured defect.
    """
    for checkout in (project.resolve(), *project.resolve().parents):
        if not (checkout / ".git").exists():
            continue
        source = _worktree_source(checkout)
        if source is None:
            return None
        # A developer worktree may already own a resolved environment. Keep it;
        # production lanes have none and inherit their source checkout environment.
        if (checkout / ".venv" / "bin" / "python").is_file():
            source = checkout
        venv = source / ".venv"
        if not (venv / "bin" / "python").is_file():
            raise ValueError(f"validation source environment missing: {venv}")
        return ValidationEnvironment(checkout, source, venv)
    return None
