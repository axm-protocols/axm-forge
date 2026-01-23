"""Architecture rules — AST-based structural analysis."""

import ast
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

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
    """
    imports: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
            for alias in node.names:
                if node.module:
                    imports.append(f"{node.module}.{alias.name}")
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

        graph = self._build_import_graph(src_path)
        cycles = _tarjan_scc(graph)
        score = max(0, 100 - len(cycles) * 20)
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

        god_classes: list[dict[str, str | int]] = []
        py_files = _get_python_files(src_path)

        for path in py_files:
            tree = _parse_file_safe(path)
            if tree is None:
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
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
                        god_classes.append(
                            {
                                "name": node.name,
                                "file": str(path.relative_to(src_path)),
                                "lines": lines,
                                "methods": methods,
                            }
                        )

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


@dataclass
class CouplingMetricRule(ProjectRule):
    """Measure module coupling via fan-in/fan-out analysis."""

    max_avg_coupling: int = 10

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
                details={"max_fan_out": 0, "avg_coupling": 0.0, "score": 100},
            )

        # Calculate fan-out (imports per module)
        fan_out: dict[str, int] = {}
        fan_in: dict[str, int] = defaultdict(int)
        py_files = _get_python_files(src_path)

        for path in py_files:
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
            return CheckResult(
                rule_id=self.rule_id,
                passed=True,
                message="No modules to analyze",
                severity=Severity.INFO,
                details={"max_fan_out": 0, "avg_coupling": 0.0, "score": 100},
            )

        max_fan_out = max(fan_out.values()) if fan_out else 0
        max_fan_in = max(fan_in.values()) if fan_in else 0
        avg_coupling = sum(fan_out.values()) / len(fan_out) if fan_out else 0.0

        score = max(0, 100 - int(avg_coupling * 5))
        passed = avg_coupling <= self.max_avg_coupling

        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=f"Avg coupling: {avg_coupling:.1f} (max fan-out: {max_fan_out})",
            severity=Severity.WARNING if not passed else Severity.INFO,
            details={
                "max_fan_out": max_fan_out,
                "max_fan_in": max_fan_in,
                "avg_coupling": round(avg_coupling, 2),
                "score": score,
            },
            fix_hint="Reduce imports by consolidating or using dependency injection"
            if not passed
            else None,
        )
