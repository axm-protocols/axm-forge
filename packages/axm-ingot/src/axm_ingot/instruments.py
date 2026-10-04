"""Explicit instrument commands with no environment discovery or installation."""

from __future__ import annotations

import os
from pathlib import Path

__all__ = ["instrument_command"]


def instrument_command(
    command: list[str],
    *,
    interpreter: str,
    package_root: str,
    pythonpath: tuple[str, ...],
) -> tuple[list[str], dict[str, str]]:
    """Build a command from trusted inputs, never probing or bootstrapping venvs.

    The interpreter path stays lexical for venv activation. PYTHONPATH contains
    only declared paths, in declared order. Missing Python modules fail in that
    interpreter; other instruments must exist beside it.
    """
    python = Path(interpreter)
    if not python.is_absolute() or not python.is_file():
        raise ValueError(f"declared instrument interpreter missing: {python}")
    if not Path(package_root).is_absolute() or not command:
        raise ValueError("instrument requires an absolute package root and command")
    if any(not Path(path).is_absolute() for path in pythonpath):
        raise ValueError("instrument pythonpath must be absolute")
    if Path(command[0]).name != command[0] or command[0] == "uv":
        raise ValueError("instrument must be a name; uv bootstrapping is forbidden")
    if command[0] in {"python", "pytest", "ruff", "mypy", "deptry", "bandit"}:
        prefix = (
            [str(python)] if command[0] == "python" else [str(python), "-m", command[0]]
        )
    else:
        binary = python.parent / command[0]
        if not binary.is_file() or not binary.resolve().is_relative_to(
            python.parent.resolve()
        ):
            raise ValueError(f"declared instrument missing: {binary}")
        prefix = [str(binary)]
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(dict.fromkeys(pythonpath))
    env["PATH"] = str(python.parent) + os.pathsep + env.get("PATH", "")
    env.pop("VIRTUAL_ENV", None)
    env.pop("UV_PROJECT_ENVIRONMENT", None)
    return [*prefix, *command[1:]], env
