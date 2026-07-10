"""Best-effort code metrics for a package: LOC + module/function/class counts.

LOC is counted from ``src/**/*.py`` (filesystem only). Structural counts come
from axm-ast's ``ContextTool`` (already a dependency). Designed to feed a
``kind="code"`` quality-history line; every failure is swallowed so it can never
break an audit.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

__all__ = ["collect_code_metrics"]

_GIT_TIMEOUT_S = 10


def _count_commits(root: Path) -> int | None:
    """Total commits that touched this package's subtree on HEAD; None on failure.

    Scoped to the package dir so a monorepo reports per-package activity, not the
    whole repo. Best-effort — git absent / not a repo / timeout → None.
    """
    git = shutil.which("git")
    if git is None:
        return None
    try:
        proc = subprocess.run(  # noqa: S603 - resolved git path, fixed args, path is a resolved dir
            [git, "rev-list", "--count", "HEAD", "--", str(root)],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    out = proc.stdout.strip()
    return int(out) if proc.returncode == 0 and out.isdigit() else None


def _count_loc(root: Path) -> int | None:
    """Non-blank lines across ``src/**/*.py`` (or ``*.py``), skipping tests/.venv."""
    base = root / "src" if (root / "src").is_dir() else root
    total = 0
    found = False
    for py in base.rglob("*.py"):
        path_str = str(py)
        if "/.venv/" in path_str or "/tests/" in path_str:
            continue
        found = True
        try:
            lines = py.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        total += sum(1 for line in lines if line.strip())
    return total if found else None


def _structural_counts(path: str) -> dict[str, int]:
    """modules/functions/classes via axm-ast ContextTool; {} on any failure."""
    try:
        from axm_ast.tools.context import ContextTool

        result = ContextTool().execute(path=path, depth=0)
        patterns = (result.data or {}).get("patterns", {}) if result.success else {}
    except Exception:  # noqa: BLE001 - metrics must never break an audit
        return {}
    if not isinstance(patterns, dict):
        return {}
    out: dict[str, int] = {}
    for src_key, dst in (
        ("module_count", "modules"),
        ("function_count", "functions"),
        ("class_count", "classes"),
    ):
        value = patterns.get(src_key)
        if isinstance(value, (int, float)):
            out[dst] = int(value)
    return out


def collect_code_metrics(path: str) -> dict[str, object]:
    """Return ``{lines, modules, functions, classes, commits}`` (absent if unknown)."""
    root = Path(path).resolve()
    metrics: dict[str, object] = {}
    loc = _count_loc(root)
    if loc is not None:
        metrics["lines"] = loc
    commits = _count_commits(root)
    if commits is not None:
        metrics["commits"] = commits
    metrics.update(_structural_counts(path))
    return metrics
