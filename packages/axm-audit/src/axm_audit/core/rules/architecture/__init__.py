"""Architecture rules — AST-based structural analysis."""

from __future__ import annotations

import ast
import logging
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from axm_audit.core.rules._helpers import (
    get_ast_cache,
    get_python_files,
    parse_file_safe,
)
from axm_audit.core.rules.architecture.coupling import (
    _compute_coupling_metrics,
    _get_module_name,
    _resolve_coupling_severity,
    extract_imports,
    read_coupling_config,
    strip_prefix,
    tarjan_scc,
)
from axm_audit.core.rules.base import ProjectRule, register_rule
from axm_audit.models.results import CheckResult, Severity

logger = logging.getLogger(__name__)


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

        text_lines = [f"     \u2022 {' \u2192 '.join(strip_prefix(c))}" for c in cycles]

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
        cycles = tarjan_scc(graph)
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
            for imp in extract_imports(tree):
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
        if hasattr(node, "end_lineno") and node.end_lineno:
            lines = node.end_lineno - node.lineno + 1
        else:
            lines = 0

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

        threshold, overrides, orchestrator_bonus, multiplier = read_coupling_config(
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
