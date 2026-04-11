"""Architecture rules — AST-based structural analysis."""

from __future__ import annotations

import ast
import logging
import tomllib
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from axm_audit.core.rules._helpers import (
    get_ast_cache,
    get_python_files,
    parse_file_safe,
)
from axm_audit.core.rules.base import ProjectRule, register_rule
from axm_audit.models.results import CheckResult, Severity

logger = logging.getLogger(__name__)


def _get_module_name(path: Path, src_root: Path) -> str:
    """Convert file path to module name relative to src root."""
    rel_path = path.relative_to(src_root)
    parts = list(rel_path.parts)
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = parts[-1].replace(".py", "")
    return ".".join(parts) if parts else ""


def _extract_imports(tree: ast.Module) -> list[str]:
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


def _tarjan_scc(graph: dict[str, set[str]]) -> list[list[str]]:
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

            # All neighbors processed — "return" from this frame.
            if state.lowlink[node] == state.index[node]:
                state.pop_scc(node)

            call_stack.pop()
            if call_stack:
                parent = call_stack[-1][0]
                state.lowlink[parent] = min(state.lowlink[parent], state.lowlink[node])

    return state.sccs


@dataclass
@register_rule("architecture")
class CircularImportRule(ProjectRule):
    """Detect circular imports via import graph + Tarjan's SCC algorithm."""

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule."""
        return "ARCH_CIRCULAR"

    def check(self, project_path: Path) -> CheckResult:
        """Check for circular imports in the project."""
        early = self.check_src(project_path)
        if early is not None:
            return early

        src_path = project_path / "src"
        cycles, score = self._analyze_cycles(src_path)
        passed = len(cycles) == 0

        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=f"{len(cycles)} circular import(s) found",
            severity=Severity.ERROR if not passed else Severity.INFO,
            details={"cycles": cycles, "score": score},
            fix_hint="Break cycles by using lazy imports or restructuring"
            if cycles
            else None,
        )

    def _analyze_cycles(self, src_path: Path) -> tuple[list[list[str]], int]:
        """Build import graph and detect cycles."""
        graph = self._build_import_graph(src_path)
        cycles = _tarjan_scc(graph)
        score = max(0, 100 - len(cycles) * 20)
        return cycles, score

    def _build_import_graph(self, src_path: Path) -> dict[str, set[str]]:
        """Build the module import graph from source files."""
        graph: dict[str, set[str]] = defaultdict(set)

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
            for imp in _extract_imports(tree):
                graph[module_name].add(imp)
            if module_name not in graph:
                graph[module_name] = set()

        return dict(graph)


@dataclass
@register_rule("architecture")
class GodClassRule(ProjectRule):
    """Detect god classes (too many lines or methods)."""

    max_lines: int = 500
    max_methods: int = 15

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule."""
        return "ARCH_GOD_CLASS"

    def check(self, project_path: Path) -> CheckResult:
        """Check for god classes in the project."""
        early = self.check_src(project_path)
        if early is not None:
            return early

        src_path = project_path / "src"

        god_classes = self._find_god_classes(src_path)

        score = max(0, 100 - len(god_classes) * 15)
        passed = len(god_classes) == 0

        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=f"{len(god_classes)} god class(es) found",
            severity=Severity.WARNING if not passed else Severity.INFO,
            details={"god_classes": god_classes, "score": score},
            fix_hint="Split large classes into smaller, focused classes"
            if god_classes
            else None,
        )

    def _find_god_classes(self, src_path: Path) -> list[dict[str, str | int]]:
        """Identify god classes in the source directory."""
        god_classes: list[dict[str, str | int]] = []
        py_files = get_python_files(src_path)

        for path in py_files:
            cache = get_ast_cache()
            tree = cache.get_or_parse(path) if cache else parse_file_safe(path)
            if tree is None:
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    self._check_class_node(node, path, src_path, god_classes)

        return god_classes

    def _check_class_node(
        self,
        node: ast.ClassDef,
        file_path: Path,
        src_root: Path,
        results: list[dict[str, str | int]],
    ) -> None:
        """Analyze a single class node for god class metrics."""
        # Count lines
        if hasattr(node, "end_lineno") and node.end_lineno:
            lines = node.end_lineno - node.lineno + 1
        else:
            lines = 0

        # Count methods
        methods = sum(
            1
            for child in node.body
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef)
        )

        if lines > self.max_lines or methods > self.max_methods:
            results.append(
                {
                    "name": node.name,
                    "file": str(file_path.relative_to(src_root)),
                    "lines": lines,
                    "methods": methods,
                }
            )


def _classify_module_role(
    module_name: str,
    imports: list[str],
    src_path: Path,
) -> str:
    """Classify a module as ``"orchestrator"`` or ``"leaf"``.

    A module is an orchestrator if it imports from >= 3 distinct sibling
    subpackages within the project namespace.  Only intra-project imports
    are considered (external/stdlib imports are ignored).
    """
    # Detect internal package prefix from src_path contents
    internal_prefixes: list[str] = []
    for child in src_path.iterdir():
        if child.is_dir() and (child / "__init__.py").exists():
            internal_prefixes.append(child.name)

    # Determine the parent namespace of the current module.
    # Modules must be at depth >= 3 (e.g. pkg.sub.mod) to have
    # meaningful subpackage siblings.  Top-level modules (pkg.mod)
    # are always leaf — they sit in a flat package.
    _min_subpackage_depth = 3
    parts = module_name.split(".")
    if len(parts) < _min_subpackage_depth:
        return "leaf"
    parent = ".".join(parts[:-1])

    # Count distinct sibling modules/subpackages under the same parent
    siblings: set[str] = set()
    for imp in imports:
        # Skip external imports
        if not any(
            imp == pfx or imp.startswith(f"{pfx}.") for pfx in internal_prefixes
        ):
            continue
        imp_parts = imp.split(".")
        # Check if this import shares the same parent
        if len(imp_parts) >= len(parts):
            imp_parent = ".".join(imp_parts[: len(parts) - 1])
            if imp_parent == parent:
                sibling_name = imp_parts[len(parts) - 1]
                siblings.add(sibling_name)

    # Exclude the module itself from sibling count
    own_name = parts[-1]
    siblings.discard(own_name)

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
        imports = _extract_imports(tree)
        fan_out[module_name] = len(set(imports))
        imports_map[module_name] = imports
        for imp in imports:
            fan_in[imp] += 1

    return fan_out, fan_in, imports_map


_COUPLING_DEFAULT_THRESHOLD = 10
_COUPLING_DEFAULT_ORCHESTRATOR_BONUS = 5


def _read_coupling_config(project_path: Path) -> tuple[int, dict[str, int], int]:
    """Read coupling thresholds from ``[tool.axm-audit.coupling]`` in pyproject.toml.

    Returns:
        ``(fan_out_threshold, overrides, orchestrator_bonus)`` — falls back to
        defaults on any error.
    """
    pyproject = project_path / "pyproject.toml"
    if not pyproject.exists():
        return _COUPLING_DEFAULT_THRESHOLD, {}, _COUPLING_DEFAULT_ORCHESTRATOR_BONUS

    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return _COUPLING_DEFAULT_THRESHOLD, {}, _COUPLING_DEFAULT_ORCHESTRATOR_BONUS

    section = data.get("tool", {}).get("axm-audit", {}).get("coupling", {})

    raw_threshold = section.get("fan_out_threshold", _COUPLING_DEFAULT_THRESHOLD)
    try:
        threshold = int(raw_threshold)
    except (TypeError, ValueError):
        threshold = _COUPLING_DEFAULT_THRESHOLD

    if threshold < 0:
        threshold = _COUPLING_DEFAULT_THRESHOLD

    raw_overrides = section.get("overrides", {})
    overrides: dict[str, int] = {}
    if isinstance(raw_overrides, dict):
        try:
            overrides = {str(k): int(v) for k, v in raw_overrides.items()}
        except (TypeError, ValueError):
            overrides = {}

    raw_bonus = section.get("orchestrator_bonus", _COUPLING_DEFAULT_ORCHESTRATOR_BONUS)
    try:
        bonus = int(raw_bonus)
    except (TypeError, ValueError):
        bonus = _COUPLING_DEFAULT_ORCHESTRATOR_BONUS

    if bonus < 0:
        bonus = _COUPLING_DEFAULT_ORCHESTRATOR_BONUS

    return threshold, overrides, bonus


def _build_coupling_result(  # noqa: PLR0913
    fan_out: dict[str, int],
    fan_in: dict[str, int],
    threshold: int,
    overrides: dict[str, int] | None = None,
    *,
    orchestrator_bonus: int = 0,
    imports_map: dict[str, list[str]] | None = None,
    src_path: Path | None = None,
) -> dict[str, Any]:
    """Compute coupling summary from fan metrics."""
    _overrides = overrides or {}
    _imports_map = imports_map or {}

    def _effective_threshold(name: str) -> tuple[int, str]:
        """Return ``(effective_threshold, role)`` for *name*."""
        if name in _overrides:
            return _overrides[name], _classify_module_role(
                name,
                _imports_map.get(name, []),
                src_path,
            ) if src_path else "leaf"
        for key, val in _overrides.items():
            if name.endswith(f".{key}") or name == key:
                return val, _classify_module_role(
                    name,
                    _imports_map.get(name, []),
                    src_path,
                ) if src_path else "leaf"

        role = "leaf"
        if src_path and orchestrator_bonus:
            role = _classify_module_role(
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
            over.append(
                {
                    "module": name,
                    "fan_out": fo,
                    "role": role,
                    "effective_threshold": eff,
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

    return _build_coupling_result(
        fan_out,
        fan_in,
        threshold,
        overrides,
        orchestrator_bonus=orchestrator_bonus,
        imports_map=imports_map,
        src_path=src_path,
    )


@dataclass
@register_rule("architecture")
class CouplingMetricRule(ProjectRule):
    """Measure module coupling via fan-in/fan-out analysis.

    Scores based on the number of modules whose fan-out exceeds
    the threshold: ``score = 100 - N(over) * 5``.
    """

    fan_out_threshold: int = 10

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule."""
        return "ARCH_COUPLING"

    def check(self, project_path: Path) -> CheckResult:
        """Check coupling metrics for the project."""
        early = self.check_src(project_path)
        if early is not None:
            return early

        src_path = project_path / "src"

        threshold, overrides, orchestrator_bonus = _read_coupling_config(project_path)
        metrics = _compute_coupling_metrics(
            src_path,
            threshold,
            overrides,
            orchestrator_bonus,
        )
        n_over: int = metrics["n_over_threshold"]
        over: list[dict[str, Any]] = metrics["over_threshold"]
        avg: float = metrics["avg_coupling"]
        score = max(0, 100 - n_over * 5)

        if n_over:
            penalty = n_over * 5
            msg = f"Coupling: {n_over} module(s) above threshold (-{penalty} pts)"
        else:
            max_fo = metrics["max_fan_out"]
            msg = f"Coupling: 0 modules above threshold (max fan-out: {max_fo})"

        # Build fix_hint with module listing
        hint = None
        if over:
            lines = [f"  \u2022 {m['module']} (fan-out: {m['fan_out']})" for m in over]
            hint = "Reduce imports in:\n" + "\n".join(lines)

        return CheckResult(
            rule_id=self.rule_id,
            passed=n_over == 0,
            message=msg,
            severity=Severity.WARNING if n_over else Severity.INFO,
            details={
                "max_fan_out": metrics["max_fan_out"],
                "max_fan_in": metrics["max_fan_in"],
                "avg_coupling": round(avg, 2),
                "score": score,
                "n_over_threshold": n_over,
                "over_threshold": over,
            },
            fix_hint=hint,
        )
