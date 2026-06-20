"""Best-effort code metrics for a package: LOC + module/function/class counts.

LOC is counted from ``src/**/*.py`` (filesystem only). Structural counts come
from axm-ast's ``ContextTool`` (already a dependency). Designed to feed a
``kind="code"`` quality-history line; every failure is swallowed so it can never
break an audit.
"""

from __future__ import annotations

from pathlib import Path

__all__ = ["collect_code_metrics"]


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
    """Return ``{lines, modules, functions, classes}`` (keys absent if unknown)."""
    metrics: dict[str, object] = {}
    loc = _count_loc(Path(path).resolve())
    if loc is not None:
        metrics["lines"] = loc
    metrics.update(_structural_counts(path))
    return metrics
