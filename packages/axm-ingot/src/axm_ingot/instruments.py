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
    the primary package source, then declared supplemental paths in order.
    Missing Python modules fail in that interpreter; other instruments must
    exist beside it.
    """
    python = Path(interpreter)
    if not python.is_absolute() or not python.is_file():
        raise ValueError(f"declared instrument interpreter missing: {python}")
    if not Path(package_root).is_absolute() or not command:
        raise ValueError("instrument requires an absolute package root and command")
    if any(not Path(path).is_absolute() for path in pythonpath):
        raise ValueError("instrument pythonpath must be absolute")
    prefix = _instrument_prefix(command[0], python)
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(_source_overlay(package_root, pythonpath))
    env["PATH"] = str(python.parent) + os.pathsep + env.get("PATH", "")
    env.pop("PYTHONHOME", None)
    env["PYTHONNOUSERSITE"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.pop("VIRTUAL_ENV", None)
    env.pop("UV_PROJECT_ENVIRONMENT", None)
    return [*prefix, *command[1:]], env


def _instrument_prefix(name: str, python: Path) -> list[str]:
    """Refuse installer and path escape commands; require named instruments."""
    if Path(name).name != name or name == "uv":
        raise ValueError("instrument must be a name; uv bootstrapping is forbidden")
    if name == "python":
        return [str(python)]
    if name in {"pytest", "ruff", "mypy", "deptry", "bandit"}:
        return [str(python), "-m", name]
    binary = python.parent / name
    if not binary.is_file() or not binary.resolve().is_relative_to(
        python.parent.resolve()
    ):
        raise ValueError(f"declared instrument missing: {binary}")
    return [str(binary)]


def _source_overlay(package_root: str, pythonpath: tuple[str, ...]) -> tuple[str, ...]:
    """Prepend the primary candidate source without expanding declared authority."""
    root = Path(package_root).resolve()
    candidate = root / "src"
    source = candidate.resolve() if candidate.is_dir() else root
    extras = tuple(str(Path(path).resolve()) for path in pythonpath)
    if not source.is_relative_to(root) and str(source) not in extras:
        raise ValueError(f"candidate source escapes declared package root: {source}")
    return tuple(dict.fromkeys((str(source), *extras)))
