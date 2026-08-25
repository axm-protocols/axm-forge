"""Fix-corpus loader factory and collection guard.

This conftest is a *fixture module*, not a test module. It exposes
``fix_corpus_case(name)`` for tests under ``tests/unit`` and
``tests/integration`` to consume a known-good pre/post-fix mini-package.

It also disables pytest collection for the ``input/`` and ``expected/``
trees under each case directory (they contain ``test_*.py`` files that
represent fixture data, not real tests).
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

__all__ = ["fix_corpus_case"]

CORPUS_ROOT = Path(__file__).parent

# Prevent pytest from collecting fixture trees (each case has its own
# ``input/`` and ``expected/`` directory tree filled with ``test_*.py``
# files that are fixture data, not tests). AC7.
collect_ignore_glob = ["*/input", "*/expected"]


def fix_corpus_case(name: str) -> tuple[Path, Path]:
    """Materialise the named fix-corpus case into a fresh temp directory.

    Copies ``tests/fixtures/fix_corpus/<name>/input/`` to a new temp
    directory, initialises a git repo (so ``axm-audit fix`` can run),
    and returns ``(tmp_pkg, expected_path)`` where ``expected_path``
    points at the on-disk ``expected/`` tree for comparison.

    The caller is responsible for cleanup; we use ``tempfile.mkdtemp``
    rather than ``tmp_path`` so the factory can be invoked from plain
    functions, not just pytest fixtures.
    """
    case_dir = CORPUS_ROOT / name
    input_dir = case_dir / "input"
    expected_dir = case_dir / "expected"
    if not input_dir.is_dir():
        raise FileNotFoundError(f"fix-corpus case {name!r} has no input/ tree")
    if not expected_dir.is_dir():
        raise FileNotFoundError(f"fix-corpus case {name!r} has no expected/ tree")

    tmp_root = Path(tempfile.mkdtemp(prefix=f"fix_corpus_{name}_"))
    tmp_pkg = tmp_root / name
    shutil.copytree(input_dir, tmp_pkg)

    subprocess.run(
        ["git", "init", "--quiet"],
        cwd=tmp_pkg,
        check=True,
        capture_output=True,
    )
    return tmp_pkg, expected_dir
