"""Structural branch diff — symbol-level comparison between git refs.

Uses git worktrees to checkout both refs and ``analyze_package()`` on
each version, then compares symbol sets by name + signature.

Example:
    >>> from axm_ast.core.structural_diff import structural_diff
    >>> result = structural_diff(Path("src/mylib"), "main", "feature")
    >>> result["added"]
    [{"name": "new_func", "kind": "function", "file": "core.py", ...}]
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Any

from axm_ast.core.analyzer import analyze_package

__all__ = ["structural_diff"]


def _find_project_root(pkg_path: Path) -> Path:
    """Walk up from *pkg_path* to find the git repository root.

    Args:
        pkg_path: Absolute path to the package directory.

    Returns:
        The git repository root.

    Raises:
        RuntimeError: If not inside a git repository.
    """
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=pkg_path,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        msg = "Not a git repository"
        raise RuntimeError(msg)
    # Resolve symlinks (macOS /var → /private/var) for consistent paths.
    return Path(result.stdout.strip()).resolve()


def _validate_ref(project_root: Path, ref: str) -> bool:
    """Check if a git ref exists.

    Args:
        project_root: Git repository root.
        ref: Git ref to validate (branch, tag, commit).

    Returns:
        True if the ref exists.
    """
    result = subprocess.run(
        ["git", "rev-parse", "--verify", ref],
        cwd=project_root,
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


def _extract_symbols(
    pkg_path: Path,
) -> dict[tuple[str, str], dict[str, Any]]:
    """Extract all symbols from a package as a keyed dict.

    Args:
        pkg_path: Absolute path to the package directory.

    Returns:
        Dict mapping ``(module_name, symbol_name)`` to symbol metadata.
    """
    pkg_path = pkg_path.resolve()
    pkg = analyze_package(pkg_path)
    symbols: dict[tuple[str, str], dict[str, Any]] = {}

    for mod in pkg.modules:
        # Build relative module name
        try:
            mod_rel = mod.path.relative_to(pkg_path)
        except ValueError:
            continue
        mod_name = str(mod_rel)

        for fn in mod.functions:
            key = (mod_name, fn.name)
            symbols[key] = {
                "name": fn.name,
                "kind": str(fn.kind.value),
                "file": mod_name,
                "signature": fn.signature,
            }

        for cls in mod.classes:
            key = (mod_name, cls.name)
            # Build a signature-like string for class comparison
            methods_str = ", ".join(m.name for m in cls.methods)
            bases_str = ", ".join(cls.bases) if cls.bases else ""
            cls_sig = f"class {cls.name}({bases_str}): [{methods_str}]"
            symbols[key] = {
                "name": cls.name,
                "kind": "class",
                "file": mod_name,
                "signature": cls_sig,
            }

    return symbols


def _extract_symbols_at_ref(
    project_root: Path,
    pkg_rel: Path,
    ref: str,
) -> dict[tuple[str, str], dict[str, Any]] | str:
    """Extract symbols from a package at a specific git ref via worktree.

    Args:
        project_root: Git repository root.
        pkg_rel: Package path relative to project root.
        ref: Git ref (branch, tag, commit).

    Returns:
        Symbol dict on success, or error message string on failure.
    """
    worktree_dir = None
    try:
        worktree_dir = tempfile.mkdtemp(prefix="axm_diff_")
        result = subprocess.run(
            ["git", "worktree", "add", "--detach", worktree_dir, ref],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return f"Failed to create worktree for ref '{ref}'"

        pkg_in_wt = Path(worktree_dir) / pkg_rel
        if not pkg_in_wt.is_dir():
            return f"Package not found in ref '{ref}': {pkg_rel}"

        return _extract_symbols(pkg_in_wt)
    finally:
        if worktree_dir is not None:
            subprocess.run(
                ["git", "worktree", "remove", "--force", worktree_dir],
                cwd=project_root,
                capture_output=True,
                check=False,
            )


def _compute_diff(
    base_symbols: dict[tuple[str, str], dict[str, Any]],
    head_symbols: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any]:
    """Compute the structural diff between two symbol sets.

    Args:
        base_symbols: Symbols from the base ref.
        head_symbols: Symbols from the head ref.

    Returns:
        Dict with ``added``, ``removed``, ``modified``, ``summary``.
    """
    base_keys = set(base_symbols.keys())
    head_keys = set(head_symbols.keys())

    added_keys = head_keys - base_keys
    removed_keys = base_keys - head_keys
    common_keys = base_keys & head_keys

    added = sorted(
        [head_symbols[k] for k in added_keys],
        key=lambda s: (s["file"], s["name"]),
    )
    removed = sorted(
        [base_symbols[k] for k in removed_keys],
        key=lambda s: (s["file"], s["name"]),
    )

    modified: list[dict[str, Any]] = []
    for key in sorted(common_keys):
        base_sig = base_symbols[key]["signature"]
        head_sig = head_symbols[key]["signature"]
        if base_sig != head_sig:
            modified.append(
                {
                    "name": head_symbols[key]["name"],
                    "kind": head_symbols[key]["kind"],
                    "file": head_symbols[key]["file"],
                    "old_signature": base_sig,
                    "new_signature": head_sig,
                }
            )

    return {
        "added": added,
        "removed": removed,
        "modified": modified,
        "summary": {
            "added": len(added),
            "removed": len(removed),
            "modified": len(modified),
        },
    }


def _validate_diff_inputs(
    pkg_path: Path,
    base: str,
    head: str,
) -> dict[str, str] | tuple[Path, Path]:
    """Validate inputs for structural diff.

    Returns:
        On success: (project_root, pkg_rel) tuple.
        On error: dict with ``error`` key.
    """
    try:
        project_root = _find_project_root(pkg_path)
    except RuntimeError as exc:
        return {"error": str(exc)}

    if not _validate_ref(project_root, base):
        return {"error": f"Invalid git ref: {base}"}
    if not _validate_ref(project_root, head):
        return {"error": f"Invalid git ref: {head}"}

    try:
        pkg_rel = pkg_path.relative_to(project_root)
    except ValueError:
        return {"error": "Package path is not inside the git repository"}

    return project_root, pkg_rel


def structural_diff(
    pkg_path: Path,
    base: str,
    head: str,
) -> dict[str, Any]:
    """Compare two git refs at symbol level.

    Uses git worktrees to checkout the *base* ref, runs
    ``analyze_package()`` on both versions, and diffs the
    symbol sets.

    Args:
        pkg_path: Path to the package directory.
        base: Base git ref (branch, tag, or commit).
        head: Head git ref (branch, tag, or commit).

    Returns:
        Dict with ``added``, ``removed``, ``modified``, and
        ``summary`` keys.  On error, returns a dict with an
        ``error`` key.

    Example:
        >>> result = structural_diff(Path("src/mylib"), "main", "feature")
        >>> len(result["added"])
        3
    """
    pkg_path = pkg_path.resolve()

    validated = _validate_diff_inputs(pkg_path, base, head)
    if isinstance(validated, dict):
        return validated
    project_root, pkg_rel = validated

    head_symbols = _extract_symbols_at_ref(project_root, pkg_rel, head)
    if isinstance(head_symbols, str):
        return {"error": head_symbols}

    base_symbols = _extract_symbols_at_ref(project_root, pkg_rel, base)
    if isinstance(base_symbols, str):
        return {"error": base_symbols}

    return _compute_diff(base_symbols, head_symbols)
