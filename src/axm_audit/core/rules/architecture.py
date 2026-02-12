"""Architecture rules — AST-based structural analysis."""

import ast
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from axm_audit.core.rules.base import ProjectRule
from axm_audit.models.results import CheckResult, Severity


def _get_python_files(directory: Path) -> list[Path]:
    """Get all Python files in a directory recursively."""
    if not directory.exists():
        return []
    return list(directory.rglob("*.py"))


def _parse_file_safe(path: Path) -> ast.Module | None:
    """Parse a Python file, returning None on error."""
    try:
        return ast.parse(path.read_text(), filename=str(path))
    except (SyntaxError, UnicodeDecodeError):
        return None


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
    """
    imports: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
    return imports


def _tarjan_scc(graph: dict[str, set[str]]) -> list[list[str]]:
    """Find strongly connected components using Tarjan's algorithm."""
    index_counter = [0]
    stack: list[str] = []
    lowlink: dict[str, int] = {}
    index: dict[str, int] = {}
    on_stack: dict[str, bool] = {}
    sccs: list[list[str]] = []

    def strongconnect(node: str) -> None:
        """Process a node for SCC detection using Tarjan's algorithm."""
        index[node] = index_counter[0]
        lowlink[node] = index_counter[0]
        index_counter[0] += 1
        stack.append(node)
        on_stack[node] = True

        for neighbor in graph.get(node, set()):
            if neighbor not in index:
                strongconnect(neighbor)
                lowlink[node] = min(lowlink[node], lowlink[neighbor])
            elif on_stack.get(neighbor, False):
                lowlink[node] = min(lowlink[node], index[neighbor])

        if lowlink[node] == index[node]:
            scc: list[str] = []
            while True:
                w = stack.pop()
                on_stack[w] = False
                scc.append(w)
                if w == node:
                    break
            if len(scc) > 1:
                sccs.append(scc)

    for node in graph:
        if node not in index:
            strongconnect(node)

    return sccs


@dataclass
class CircularImportRule(ProjectRule):
    """Detect circular imports via import graph + Tarjan's SCC algorithm."""

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule."""
        return "ARCH_CIRCULAR"

    def check(self, project_path: Path) -> CheckResult:
        """Check for circular imports in the project."""
        src_path = project_path / "src"
        if not src_path.exists():
            return self._empty_result()

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

    def _empty_result(self) -> CheckResult:
        """Return result when src/ doesn't exist."""
        return CheckResult(
            rule_id=self.rule_id,
            passed=True,
            message="src/ directory not found",
            severity=Severity.INFO,
            details={"cycles": [], "score": 100},
        )

    def _build_import_graph(self, src_path: Path) -> dict[str, set[str]]:
        """Build the module import graph from source files."""
        graph: dict[str, set[str]] = defaultdict(set)

        for path in _get_python_files(src_path):
            if path.name == "__init__.py":
                continue
            tree = _parse_file_safe(path)
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
        src_path = project_path / "src"
        if not src_path.exists():
            return CheckResult(
                rule_id=self.rule_id,
                passed=True,
                message="src/ directory not found",
                severity=Severity.INFO,
                details={"god_classes": [], "score": 100},
            )

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
        py_files = _get_python_files(src_path)

        for path in py_files:
            tree = _parse_file_safe(path)
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


def _compute_coupling_metrics(
    src_path: Path,
    threshold: int = 10,
) -> dict[str, Any]:
    """Compute fan-in/fan-out coupling metrics for all modules."""
    fan_out: dict[str, int] = {}
    fan_in: dict[str, int] = defaultdict(int)

    for path in _get_python_files(src_path):
        tree = _parse_file_safe(path)
        if tree is None:
            continue
        module_name = _get_module_name(path, src_path)
        if not module_name:
            continue
        imports = _extract_imports(tree)
        fan_out[module_name] = len(set(imports))
        for imp in imports:
            fan_in[imp] += 1

    if not fan_out:
        return {
            "max_fan_out": 0,
            "max_fan_in": 0,
            "avg_coupling": 0.0,
            "n_over_threshold": 0,
            "over_threshold": [],
        }

    over_unsorted = [
        {"module": name, "fan_out": fo}
        for name, fo in fan_out.items()
        if fo > threshold
    ]
    over_unsorted.sort(key=lambda x: x.get("fan_out", 0), reverse=True)  # type: ignore[return-value,arg-type]
    over = over_unsorted

    return {
        "max_fan_out": max(fan_out.values()),
        "max_fan_in": max(fan_in.values()) if fan_in else 0,
        "avg_coupling": sum(fan_out.values()) / len(fan_out),
        "n_over_threshold": len(over),
        "over_threshold": over,
    }


@dataclass
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
        src_path = project_path / "src"
        if not src_path.exists():
            return CheckResult(
                rule_id=self.rule_id,
                passed=True,
                message="src/ directory not found",
                severity=Severity.INFO,
                details={
                    "max_fan_out": 0,
                    "avg_coupling": 0.0,
                    "score": 100,
                    "n_over_threshold": 0,
                    "over_threshold": [],
                },
            )

        metrics = _compute_coupling_metrics(src_path, self.fan_out_threshold)
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
