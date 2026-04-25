"""Coupling helpers — graph algorithms and config parsing.

Public-internal API: the eight non-underscore functions below are stable
enough to be imported directly by tests within this package.  They are
not re-exported in the package root ``__all__`` because they are tools
for rule authors, not application code.
"""

from __future__ import annotations

import ast
import logging
import tomllib
from collections import defaultdict
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from axm_audit.core.rules._helpers import (
    get_ast_cache,
    get_python_files,
    parse_file_safe,
)
from axm_audit.models.results import Severity

logger = logging.getLogger(__name__)


def strip_prefix(modules: list[str]) -> list[str]:
    """Strip the common top-level package prefix from module names.

    All modules in a detected cycle belong to the same package (the graph
    only contains modules under ``src/``).  Removing the shared prefix
    cuts token count by ~49% with zero information loss.
    """
    if not modules:
        return modules
    first_dot = modules[0].find(".")
    if first_dot == -1:
        return modules
    prefix = modules[0][: first_dot + 1]
    if all(m.startswith(prefix) for m in modules):
        return [m[len(prefix) :] for m in modules]
    return modules


def _get_module_name(path: Path, src_root: Path) -> str:
    """Convert file path to module name relative to src root."""
    rel_path = path.relative_to(src_root)
    parts = list(rel_path.parts)
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = parts[-1].replace(".py", "")
    return ".".join(parts) if parts else ""


def extract_imports(tree: ast.Module) -> list[str]:
    """Extract module-level imported module names from an AST.

    Only scans top-level imports to avoid false positives from lazy/deferred
    imports inside functions (which don't cause circular import issues at runtime).

    Counts source modules, not individual imported symbols. For example,
    ``from foo import A, B`` counts as a single import of ``foo``.

    ``__future__`` imports are excluded — they are language directives,
    not real dependencies.
    """
    imports: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module != "__future__":
                imports.append(node.module)
    return imports


class _TarjanState:
    """Mutable state container for the iterative Tarjan algorithm."""

    __slots__ = ("counter", "index", "lowlink", "on_stack", "sccs", "stack")

    def __init__(self) -> None:
        self.counter = 0
        self.stack: list[str] = []
        self.lowlink: dict[str, int] = {}
        self.index: dict[str, int] = {}
        self.on_stack: dict[str, bool] = {}
        self.sccs: list[list[str]] = []

    def enter(self, node: str) -> None:
        """Register a node as visited and push it onto the SCC stack."""
        self.index[node] = self.lowlink[node] = self.counter
        self.counter += 1
        self.stack.append(node)
        self.on_stack[node] = True

    def pop_scc(self, root: str) -> None:
        """Pop nodes from the stack to form an SCC rooted at *root*."""
        scc: list[str] = []
        while True:
            w = self.stack.pop()
            self.on_stack[w] = False
            scc.append(w)
            if w == root:
                break
        if len(scc) > 1:
            self.sccs.append(scc)


def _try_advance(
    state: _TarjanState,
    node: str,
    neighbors: Iterator[str],
    graph: dict[str, set[str]],
    call_stack: list[tuple[str, Iterator[str]]],
) -> bool:
    """Try to advance to an unvisited neighbor, returning True if advanced."""
    for neighbor in neighbors:
        if neighbor not in state.index:
            state.enter(neighbor)
            call_stack.append((neighbor, iter(graph.get(neighbor, set()))))
            return True
        if state.on_stack.get(neighbor, False):
            state.lowlink[node] = min(state.lowlink[node], state.index[neighbor])
    return False


def tarjan_scc(graph: dict[str, set[str]]) -> list[list[str]]:
    """Find strongly connected components using iterative Tarjan's algorithm.

    Uses an explicit call stack instead of recursion to avoid hitting
    Python's recursion limit on large graphs (>1000 modules).
    """
    state = _TarjanState()

    for root in graph:
        if root in state.index:
            continue

        call_stack: list[tuple[str, Iterator[str]]] = []
        state.enter(root)
        call_stack.append((root, iter(graph.get(root, set()))))

        while call_stack:
            node, neighbors = call_stack[-1]

            if _try_advance(state, node, neighbors, graph, call_stack):
                continue

            if state.lowlink[node] == state.index[node]:
                state.pop_scc(node)

            call_stack.pop()
            if call_stack:
                parent = call_stack[-1][0]
                state.lowlink[parent] = min(state.lowlink[parent], state.lowlink[node])

    return state.sccs


def _detect_internal_prefixes(src_path: Path) -> list[str]:
    """Return package names found directly under *src_path*."""
    return [
        child.name
        for child in src_path.iterdir()
        if child.is_dir() and (child / "__init__.py").exists()
    ]


def _is_internal_import(imp: str, prefixes: list[str]) -> bool:
    """Return ``True`` if *imp* belongs to one of the *prefixes*."""
    return any(imp == pfx or imp.startswith(f"{pfx}.") for pfx in prefixes)


def _count_siblings(
    module_name: str,
    imports: list[str],
    internal_prefixes: list[str],
) -> set[str]:
    """Return the set of sibling subpackage names imported by *module_name*."""
    parts = module_name.split(".")
    parent = ".".join(parts[:-1])
    siblings: set[str] = set()
    for imp in imports:
        if not _is_internal_import(imp, internal_prefixes):
            continue
        imp_parts = imp.split(".")
        if len(imp_parts) >= len(parts):
            imp_parent = ".".join(imp_parts[: len(parts) - 1])
            if imp_parent == parent:
                siblings.add(imp_parts[len(parts) - 1])
    siblings.discard(parts[-1])
    return siblings


def classify_module_role(
    module_name: str,
    imports: list[str],
    src_path: Path,
) -> str:
    """Classify a module as ``"orchestrator"`` or ``"leaf"``.

    A module is an orchestrator if it imports from >= 3 distinct sibling
    subpackages within the project namespace.  Only intra-project imports
    are considered (external/stdlib imports are ignored).
    """
    _min_subpackage_depth = 3
    parts = module_name.split(".")
    if len(parts) < _min_subpackage_depth:
        return "leaf"

    internal_prefixes = _detect_internal_prefixes(src_path)
    siblings = _count_siblings(module_name, imports, internal_prefixes)

    _min_siblings_for_orchestrator = 3
    return "orchestrator" if len(siblings) >= _min_siblings_for_orchestrator else "leaf"


def _build_fan_metrics(
    src_path: Path,
) -> tuple[dict[str, int], dict[str, int], dict[str, list[str]]]:
    """Build fan-in/fan-out dicts and imports map from source files."""
    fan_out: dict[str, int] = {}
    fan_in: dict[str, int] = defaultdict(int)
    imports_map: dict[str, list[str]] = {}

    for path in get_python_files(src_path):
        if path.name == "__init__.py":
            continue
        cache = get_ast_cache()
        tree = cache.get_or_parse(path) if cache else parse_file_safe(path)
        if tree is None:
            continue
        module_name = _get_module_name(path, src_path)
        if not module_name:
            continue
        imports = extract_imports(tree)
        fan_out[module_name] = len(set(imports))
        imports_map[module_name] = imports
        for imp in imports:
            fan_in[imp] += 1

    return fan_out, fan_in, imports_map


_COUPLING_DEFAULT_THRESHOLD = 10
_COUPLING_DEFAULT_ORCHESTRATOR_BONUS = 5
_COUPLING_DEFAULT_SEVERITY_MULTIPLIER = 2


def safe_int(value: Any, default: int) -> int:
    """Convert *value* to a non-negative ``int``, returning *default* on failure."""
    try:
        result = int(value)
    except (TypeError, ValueError):
        return default
    return result if result >= 0 else default


def parse_overrides(raw: object) -> dict[str, int]:
    """Parse an overrides mapping, silently dropping invalid entries."""
    if not isinstance(raw, dict):
        return {}
    try:
        return {str(k): int(v) for k, v in raw.items()}
    except (TypeError, ValueError):
        return {}


def read_coupling_config(
    project_path: Path,
) -> tuple[int, dict[str, int], int, int]:
    """Read coupling thresholds from ``[tool.axm-audit.coupling]`` in pyproject.toml.

    Returns:
        ``(fan_out_threshold, overrides, orchestrator_bonus,
        severity_error_multiplier)`` — falls back to defaults on any error.
    """
    defaults: tuple[int, dict[str, int], int, int] = (
        _COUPLING_DEFAULT_THRESHOLD,
        {},
        _COUPLING_DEFAULT_ORCHESTRATOR_BONUS,
        _COUPLING_DEFAULT_SEVERITY_MULTIPLIER,
    )
    pyproject = project_path / "pyproject.toml"
    if not pyproject.exists():
        return defaults

    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return defaults

    section = data.get("tool", {}).get("axm-audit", {}).get("coupling", {})

    threshold = safe_int(
        section.get("fan_out_threshold", _COUPLING_DEFAULT_THRESHOLD),
        _COUPLING_DEFAULT_THRESHOLD,
    )
    overrides = parse_overrides(section.get("overrides", {}))
    bonus = safe_int(
        section.get("orchestrator_bonus", _COUPLING_DEFAULT_ORCHESTRATOR_BONUS),
        _COUPLING_DEFAULT_ORCHESTRATOR_BONUS,
    )
    multiplier = max(
        safe_int(
            section.get(
                "severity_error_multiplier", _COUPLING_DEFAULT_SEVERITY_MULTIPLIER
            ),
            _COUPLING_DEFAULT_SEVERITY_MULTIPLIER,
        ),
        1,
    )

    return threshold, overrides, bonus, multiplier


def build_coupling_result(  # noqa: PLR0913
    fan_out: dict[str, int],
    fan_in: dict[str, int],
    threshold: int,
    overrides: dict[str, int] | None = None,
    *,
    orchestrator_bonus: int = 0,
    imports_map: dict[str, list[str]] | None = None,
    src_path: Path | None = None,
    severity_error_multiplier: int = _COUPLING_DEFAULT_SEVERITY_MULTIPLIER,
) -> dict[str, Any]:
    """Compute coupling summary from fan-out / fan-in metrics.

    Classifies each over-threshold module as ``"warning"`` or ``"error"``
    based on *severity_error_multiplier*: fan-out above
    ``effective_threshold * severity_error_multiplier`` is an error,
    otherwise a warning.

    Returns a dict with keys ``max_fan_out``, ``max_fan_in``,
    ``avg_coupling``, ``n_over_threshold``, and ``over_threshold``
    (list of dicts with ``module``, ``fan_out``, ``role``,
    ``effective_threshold``, ``severity``).
    """
    _overrides = overrides or {}
    _imports_map = imports_map or {}

    def _effective_threshold(name: str) -> tuple[int, str]:
        """Return ``(effective_threshold, role)`` for *name*."""
        if name in _overrides:
            return _overrides[name], classify_module_role(
                name,
                _imports_map.get(name, []),
                src_path,
            ) if src_path else "leaf"
        for key, val in _overrides.items():
            if name.endswith(f".{key}") or name == key:
                return val, classify_module_role(
                    name,
                    _imports_map.get(name, []),
                    src_path,
                ) if src_path else "leaf"

        role = "leaf"
        if src_path and orchestrator_bonus:
            role = classify_module_role(
                name,
                _imports_map.get(name, []),
                src_path,
            )
        bonus = orchestrator_bonus if role == "orchestrator" else 0
        return threshold + bonus, role

    over: list[dict[str, Any]] = []
    for name, fo in fan_out.items():
        eff, role = _effective_threshold(name)
        if fo > eff:
            severity = "error" if fo > eff * severity_error_multiplier else "warning"
            over.append(
                {
                    "module": name,
                    "fan_out": fo,
                    "role": role,
                    "effective_threshold": eff,
                    "severity": severity,
                }
            )

    over.sort(key=lambda x: x.get("fan_out", 0), reverse=True)

    return {
        "max_fan_out": max(fan_out.values()),
        "max_fan_in": max(fan_in.values()) if fan_in else 0,
        "avg_coupling": sum(fan_out.values()) / len(fan_out),
        "n_over_threshold": len(over),
        "over_threshold": over,
    }


def _compute_coupling_metrics(
    src_path: Path,
    threshold: int = 10,
    overrides: dict[str, int] | None = None,
    orchestrator_bonus: int = 0,
    severity_error_multiplier: int = _COUPLING_DEFAULT_SEVERITY_MULTIPLIER,
) -> dict[str, Any]:
    """Compute fan-in/fan-out coupling metrics for all modules.

    ``__init__.py`` files are excluded — their purpose is to re-export
    symbols from submodules, so their fan-out is structurally high
    and not indicative of poor coupling.
    """
    fan_out, fan_in, imports_map = _build_fan_metrics(src_path)

    if not fan_out:
        return {
            "max_fan_out": 0,
            "max_fan_in": 0,
            "avg_coupling": 0.0,
            "n_over_threshold": 0,
            "over_threshold": [],
        }

    return build_coupling_result(
        fan_out,
        fan_in,
        threshold,
        overrides,
        orchestrator_bonus=orchestrator_bonus,
        imports_map=imports_map,
        src_path=src_path,
        severity_error_multiplier=severity_error_multiplier,
    )


def _resolve_coupling_severity(
    over: list[dict[str, Any]],
) -> tuple[int, int, Severity]:
    """Return ``(n_warnings, n_errors, worst_severity)`` from over-threshold entries."""
    n_warnings = sum(1 for m in over if m["severity"] == "warning")
    n_errors = sum(1 for m in over if m["severity"] == "error")
    if n_errors:
        severity = Severity.ERROR
    elif n_warnings:
        severity = Severity.WARNING
    else:
        severity = Severity.INFO
    return n_warnings, n_errors, severity
