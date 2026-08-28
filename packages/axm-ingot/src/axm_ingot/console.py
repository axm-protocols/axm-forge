"""Resolution of console scripts installed alongside the running interpreter.

``shutil.which("axm")`` answers only when the environment happens to be on
``PATH``: true under ``uv run``, false when a suite is started through the
interpreter directly (``.venv/bin/python -m pytest``) or in CI. Code that shells
out to a project CLI on the bare name therefore works or dies depending on how
it was launched — a whole e2e tier failed on ``FileNotFoundError: 'axm'`` for
exactly that reason while the binary sat next to ``sys.executable``.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

__all__ = ["console_script"]


def console_script(name: str, *, executable: str | None = None) -> str:
    """Return the path of console script *name* for the running environment.

    Looks next to the interpreter first (where an installed entry point lands),
    then falls back to ``PATH``, then to the bare name so an unusual layout — or
    a caller that genuinely wants ``PATH`` resolution at exec time — still works.

    Args:
        name: The console-script name, e.g. ``"axm"``.
        executable: Interpreter whose environment to search; defaults to
            :data:`sys.executable` (injectable for tests).

    Returns:
        An absolute path when the script was found, else *name* unchanged.
    """
    interpreter = Path(executable or sys.executable)
    candidate = interpreter.parent / name
    if candidate.is_file():
        return str(candidate)
    return shutil.which(name) or name
