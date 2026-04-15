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


def _strip_prefix(modules: list[str]) -> list[str]:
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


def _extract_imports_with_lines(tree: ast.Module) -> list[tuple[str, int]]:
    """Extract top-level imported module names with their line numbers.

    Parallel to :func:`_extract_imports` but returns ``(module, lineno)``
    tuples for violation reporting.
    """
    imports: list[tuple[str, int]] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((alias.name, node.lineno))
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module != "__future__":
                imports.append((node.module, node.lineno))
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

        text_lines = [
            f"     \u2022 {' \u2192 '.join(_strip_prefix(c))}" for c in cycles
        ]

        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=f"{len(cycles)} circular import(s) found",
            severity=Severity.ERROR if not passed else Severity.INFO,
            details={"cycles": cycles, "score": score},
            text="\n".join(text_lines) if text_lines else None,
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
        """Check for god classes in the project.

        Scans all classes under ``src/`` and flags those exceeding
        :attr:`max_lines` or :attr:`max_methods`.

        The ``text`` field uses the compact format
        ``• {basename}:{ClassName} {lines}L/{methods}M`` (one line per
        violation), or ``None`` when no god classes are found.
        """
        early = self.check_src(project_path)
        if early is not None:
            return early

        src_path = project_path / "src"

        god_classes = self._find_god_classes(src_path)

        score = max(0, 100 - len(god_classes) * 15)
        passed = len(god_classes) == 0

        text_lines = [
            f"\u2022 {Path(str(g['file'])).name}:{g['name']}"
            f" {g['lines']}L/{g['methods']}M"
            for g in god_classes
        ]

        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=f"{len(god_classes)} god class(es) found",
            severity=Severity.WARNING if not passed else Severity.INFO,
            details={"god_classes": god_classes, "score": score},
            text="\n".join(text_lines) if text_lines else None,
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


def _is_cross_package_deep_import(
    imp: str,
    prefixes: list[str],
    *,
    current_package: str,
) -> bool:
    """Return ``True`` if *imp* is a deep import into a *different* internal package.

    A "deep" import targets a sub-module (e.g. ``axm_ticket.utils``)
    rather than the package root (``axm_ticket``).  Imports within
    *current_package* are excluded — they are intra-package.
    """
    for pfx in prefixes:
        if imp == pfx or not imp.startswith(f"{pfx}."):
            continue
        # It's a deep import into *pfx* — only flag if cross-package.
        if pfx != current_package:
            return True
    return False


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
        imports = _extract_imports(tree)
        fan_out[module_name] = len(set(imports))
        imports_map[module_name] = imports
        for imp in imports:
            fan_in[imp] += 1

    return fan_out, fan_in, imports_map


_COUPLING_DEFAULT_THRESHOLD = 10
_COUPLING_DEFAULT_ORCHESTRATOR_BONUS = 5
_COUPLING_DEFAULT_SEVERITY_MULTIPLIER = 2


def _safe_int(value: Any, default: int) -> int:
    """Convert *value* to a non-negative ``int``, returning *default* on failure."""
    try:
        result = int(value)
    except (TypeError, ValueError):
        return default
    return result if result >= 0 else default


def _parse_overrides(raw: object) -> dict[str, int]:
    """Parse an overrides mapping, silently dropping invalid entries."""
    if not isinstance(raw, dict):
        return {}
    try:
        return {str(k): int(v) for k, v in raw.items()}
    except (TypeError, ValueError):
        return {}


def _read_boundary_config(project_path: Path) -> list[str]:
    """Read import-boundary allow list from ``[tool.axm-audit.import-boundary]``.

    Returns:
        List of module prefixes permitted as cross-package deep imports.
    """
    pyproject = project_path / "pyproject.toml"
    if not pyproject.exists():
        return []
    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return []
    section = data.get("tool", {}).get("axm-audit", {}).get("import-boundary", {})
    allow = section.get("allow", [])
    return list(allow) if isinstance(allow, list) else []


def _read_coupling_config(
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

    threshold = _safe_int(
        section.get("fan_out_threshold", _COUPLING_DEFAULT_THRESHOLD),
        _COUPLING_DEFAULT_THRESHOLD,
    )
    overrides = _parse_overrides(section.get("overrides", {}))
    bonus = _safe_int(
        section.get("orchestrator_bonus", _COUPLING_DEFAULT_ORCHESTRATOR_BONUS),
        _COUPLING_DEFAULT_ORCHESTRATOR_BONUS,
    )
    multiplier = max(
        _safe_int(
            section.get(
                "severity_error_multiplier", _COUPLING_DEFAULT_SEVERITY_MULTIPLIER
            ),
            _COUPLING_DEFAULT_SEVERITY_MULTIPLIER,
        ),
        1,
    )

    return threshold, overrides, bonus, multiplier


def _build_coupling_result(  # noqa: PLR0913
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

    return _build_coupling_result(
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


def _is_allowed(imp: str, allow_list: list[str]) -> bool:
    """Return ``True`` if *imp* is covered by the allow list."""
    return any(imp == a or imp.startswith(f"{a}.") for a in allow_list)


@dataclass
@register_rule("architecture")
class ImportBoundaryRule(ProjectRule):
    """Detect cross-package imports that bypass the public API surface.

    Flags imports targeting sub-modules of other packages (e.g.
    ``from axm_ticket.utils import X``) instead of the package root.
    """

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule."""
        return "import-boundary"

    def check(self, project_path: Path) -> CheckResult:
        """Scan ``src/`` for cross-package deep imports."""
        early = self.check_src(project_path)
        if early is not None:
            return early

        src_path = project_path / "src"
        prefixes = _detect_internal_prefixes(src_path)
        allow_list = _read_boundary_config(project_path)
        violations = self._collect_violations(
            project_path, src_path, prefixes, allow_list
        )
        return self._build_result(violations)

    def _collect_violations(
        self,
        project_path: Path,
        src_path: Path,
        prefixes: list[str],
        allow_list: list[str],
    ) -> list[dict[str, Any]]:
        """Scan all Python files and collect boundary violations."""
        violations: list[dict[str, Any]] = []
        for path in get_python_files(src_path):
            cache = get_ast_cache()
            tree = cache.get_or_parse(path) if cache else parse_file_safe(path)
            if tree is None:
                continue
            module_name = _get_module_name(path, src_path)
            current_package = module_name.split(".")[0] if module_name else ""
            self._check_file_imports(
                path,
                tree,
                project_path,
                prefixes,
                allow_list,
                current_package,
                violations,
            )
        return violations

    def _check_file_imports(  # noqa: PLR0913
        self,
        path: Path,
        tree: ast.Module,
        project_path: Path,
        prefixes: list[str],
        allow_list: list[str],
        current_package: str,
        violations: list[dict[str, Any]],
    ) -> None:
        """Check imports in a single file for boundary violations."""
        for imp, lineno in _extract_imports_with_lines(tree):
            if _is_allowed(imp, allow_list):
                continue
            if not _is_cross_package_deep_import(
                imp, prefixes, current_package=current_package
            ):
                continue
            target_pkg = next((p for p in prefixes if imp.startswith(f"{p}.")), "")
            violations.append(
                {
                    "file": str(path.relative_to(project_path)),
                    "line": lineno,
                    "import": imp,
                    "target_package": target_pkg,
                }
            )

    @staticmethod
    def _build_result(violations: list[dict[str, Any]]) -> CheckResult:
        """Build a :class:`CheckResult` from collected violations."""
        n = len(violations)
        score = max(0, 100 - n * 10)
        text_lines = [
            f"\u2022 {v['file']}:{v['line']} {v['import']}" for v in violations
        ]
        return CheckResult(
            rule_id="import-boundary",
            passed=n == 0,
            message=f"{n} cross-package deep import(s) found",
            severity=Severity.WARNING if n else Severity.INFO,
            details={"violations": violations, "score": score},
            text="\n".join(text_lines) if text_lines else None,
            fix_hint="Use root-level package imports instead of "
            "reaching into sub-modules"
            if violations
            else None,
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
        """Check coupling metrics for the project.

        Scans ``src/`` for import fan-out per module and compares each
        against its effective threshold (base + orchestrator bonus +
        per-module overrides).

        Returns a :class:`CheckResult` with:

        * ``text`` — one line per violation formatted as
          ``• {leaf_module} fo:{fan_out}/{threshold} {⚠|✘}``
          (``None`` when all modules pass).
        * ``details`` — full ``over_threshold`` list with FQN, fan-out,
          role, effective threshold, and severity.
        * ``fix_hint`` — human-readable remediation listing.
        """
        early = self.check_src(project_path)
        if early is not None:
            return early

        src_path = project_path / "src"

        threshold, overrides, orchestrator_bonus, multiplier = _read_coupling_config(
            project_path
        )
        metrics = _compute_coupling_metrics(
            src_path,
            threshold,
            overrides,
            orchestrator_bonus,
            severity_error_multiplier=multiplier,
        )
        n_over: int = metrics["n_over_threshold"]
        over: list[dict[str, Any]] = metrics["over_threshold"]
        avg: float = metrics["avg_coupling"]

        n_warnings, n_errors, severity = _resolve_coupling_severity(over)
        score = max(0, 100 - (n_warnings * 3 + n_errors * 5))

        if n_over:
            penalty = n_warnings * 3 + n_errors * 5
            msg = f"Coupling: {n_over} module(s) above threshold (-{penalty} pts)"
        else:
            max_fo = metrics["max_fan_out"]
            msg = f"Coupling: 0 modules above threshold (max fan-out: {max_fo})"

        # Build fix_hint with module listing
        hint = None
        if over:
            lines = [f"  \u2022 {m['module']} (fan-out: {m['fan_out']})" for m in over]
            hint = "Reduce imports in:\n" + "\n".join(lines)

        _sev = {"warning": "\u26a0", "error": "\u2718"}
        text_lines = [
            f"\u2022 {m['module'].rsplit('.', 1)[-1]}"
            f" fo:{m['fan_out']}/{m['effective_threshold']}"
            f" {_sev.get(m['severity'], '?')}"
            for m in over
        ]

        return CheckResult(
            rule_id=self.rule_id,
            passed=n_errors == 0,
            message=msg,
            severity=severity,
            details={
                "max_fan_out": metrics["max_fan_out"],
                "max_fan_in": metrics["max_fan_in"],
                "avg_coupling": round(avg, 2),
                "score": score,
                "n_over_threshold": n_over,
                "over_threshold": over,
            },
            text="\n".join(text_lines) if text_lines else None,
            fix_hint=hint,
        )
