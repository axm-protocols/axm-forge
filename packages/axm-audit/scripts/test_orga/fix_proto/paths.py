"""Path/tier/module-name helpers (no AST, no IO beyond Path inspection)."""
from __future__ import annotations

from pathlib import Path

__all__ = [
    "_abspath",
    "_safe_filename",
    "_tier_for_path",
    "_retier",
    "_module_path_for_test_file",
    "_file_depth_from_project",
]


def _abspath(p: str, project_path: Path) -> Path:
    """Normalise a finding path (which may be relative or absolute)."""
    pp = Path(p)
    return pp if pp.is_absolute() else (project_path / pp)


def _safe_filename(name: str) -> str:
    """Make a canonical filename PEP8-importable.

    Current ``FILE_NAMING`` emits ``test_<a>__<b>.py`` (``__`` separator,
    PEP 8 compliant). This function is now a near-identity defensive
    pass: it strips any legacy ``-`` separators an older audit version
    could still produce, preserving forward compatibility without
    changing the proto's behaviour on output of the current rule.
    """
    if not name.endswith(".py"):
        return name
    stem = name[:-3]
    return stem.replace("-", "__") + ".py"


def _retier(p: Path, root: Path, target_lvl: str) -> Path:
    """Compute the destination path under tests/{target_lvl}/.

    Three cases on the relative parts:

      * ``tests/<tier>/...rest...`` — substitute the tier component:
        ``parts[1] = target_lvl``.
      * ``tests/<file>.py`` — no tier component yet; inject one between
        ``tests`` and the file: result is ``tests/<target_lvl>/<file>.py``.
        Without this branch the slot-substitution path silently turned
        ``tests/test_X.py`` into ``tests/<target_lvl>`` (the ``.py``
        disappears because it was at index 1), which then surfaced as
        ``IsADirectoryError`` downstream.
      * anything not under ``tests/`` — unchanged.
    """
    rel = p.relative_to(root) if p.is_absolute() else p
    parts = list(rel.parts)
    if not parts or parts[0] != "tests":
        return root / Path(*parts)
    if len(parts) == 2:
        return root / "tests" / target_lvl / parts[1]
    parts[1] = target_lvl
    return root / Path(*parts)


def _tier_for_path(path: Path) -> str | None:
    """Return ``unit``/``integration``/``e2e`` for a test path, or None.

    Walks up the parents until a tier component is found. Tolerates
    nested test layouts like ``tests/integration/hooks/test_x.py``
    where ``path.parent.name`` is ``hooks`` rather than ``integration``.
    """
    for part in path.parts:
        if part in ("unit", "integration", "e2e"):
            return part
    return None


def _module_path_for_test_file(path: Path, project_path: Path) -> str | None:
    """Return the dotted module path used by ``from`` imports for *path*.

    For ``project/tests/integration/test_foo.py`` this returns
    ``tests.integration.test_foo``. Returns None if *path* is not under
    ``project_path/tests/``.
    """
    try:
        rel = path.resolve().relative_to(project_path.resolve())
    except ValueError:
        return None
    parts = rel.with_suffix("").parts
    if not parts or parts[0] != "tests":
        return None
    return ".".join(parts)


def _file_depth_from_project(path: Path, project_path: Path) -> int:
    """Number of path parts between *path*'s file and *project_path*.

    For ``/p/tests/unit/core/test_X.py`` under ``/p``, returns 4
    (``tests``, ``unit``, ``core``, ``test_X.py``). Independent of
    ``project_path``'s own depth. Used to compute ``depth_delta`` when
    a file is relocated, so ``Path(__file__).parents[N]`` constants
    can be re-pointed to the same ancestor.
    """
    try:
        rel = path.resolve().relative_to(project_path.resolve())
    except ValueError:
        return 0
    return len(rel.parts)
