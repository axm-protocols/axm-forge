"""Docstring coverage rule for public functions."""

from __future__ import annotations

import ast
import logging
from dataclasses import dataclass
from pathlib import Path

from axm_audit.core.rules._helpers import (
    get_ast_cache,
    get_python_files,
    parse_file_safe,
)
from axm_audit.core.rules.base import ProjectRule, register_rule
from axm_audit.models.results import CheckResult, Severity

logger = logging.getLogger(__name__)

__all__ = ["DocstringCoverageRule"]


@dataclass
@register_rule("practices")
class DocstringCoverageRule(ProjectRule):
    """Calculate docstring coverage for public functions.

    Public functions are those not starting with underscore.
    """

    min_coverage: float = 0.80

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule."""
        return "PRACTICE_DOCSTRING"

    def check(self, project_path: Path) -> CheckResult:
        """Check docstring coverage in the project."""
        early = self.check_src(project_path)
        if early is not None:
            return early

        src_path = project_path / "src"
        documented, missing = self._analyze_docstrings(src_path)
        return self._build_result(documented, missing)

    def _build_result(
        self,
        documented: int,
        missing: list[str],
    ) -> CheckResult:
        """Build CheckResult from docstring analysis."""
        total = documented + len(missing)
        coverage = documented / total if total > 0 else 1.0
        passed = coverage >= self.min_coverage
        score = int(coverage * 100)

        text: str | None = None
        if missing:
            groups: dict[str, list[str]] = {}
            for item in missing:
                file_part, _, func_name = item.rpartition(":")
                groups.setdefault(file_part, []).append(func_name)
            text_lines = [
                f"     • {path}: {', '.join(funcs)}" for path, funcs in groups.items()
            ]
            text = "\n".join(text_lines)

        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=f"Docstring coverage: {coverage:.0%} ({documented}/{total})",
            severity=Severity.WARNING if not passed else Severity.INFO,
            score=int(score),
            details={
                "coverage": round(coverage, 2),
                "total": total,
                "documented": documented,
                "missing": missing,
            },
            text=text,
            fix_hint="Add docstrings to public functions" if missing else None,
        )

    def _analyze_docstrings(self, src_path: Path) -> tuple[int, list[str]]:
        """Analyze docstring coverage in source files."""
        documented = 0
        missing: list[str] = []

        file_trees: dict[Path, ast.Module] = {}
        for path in get_python_files(src_path):
            cache = get_ast_cache()
            tree = cache.get_or_parse(path) if cache else parse_file_safe(path)
            if tree is not None:
                file_trees[path] = tree

        global_classes: dict[str, list[ast.ClassDef]] = {}
        for tree in file_trees.values():
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    global_classes.setdefault(node.name, []).append(node)

        for path, tree in file_trees.items():
            rel_path = path.relative_to(src_path)
            class_map = self._build_class_map(tree)
            doc, mis = self._check_file_docstrings(
                tree,
                rel_path,
                class_map,
                global_classes,
            )
            documented += doc
            missing.extend(mis)

        return documented, missing

    def _check_file_docstrings(
        self,
        tree: ast.Module,
        rel_path: Path,
        class_map: dict[str, ast.ClassDef],
        global_classes: dict[str, list[ast.ClassDef]],
    ) -> tuple[int, list[str]]:
        """Check docstring coverage for public functions in a single file."""
        documented = 0
        missing: list[str] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            if node.name.startswith("_"):
                continue
            if self._is_setter_or_deleter(node):
                continue
            if self.is_abstract_stub(node):
                continue
            if self._is_abstract_override(node, class_map, global_classes):
                continue

            if self._has_docstring(node):
                documented += 1
            else:
                missing.append(f"{rel_path}:{node.name}")
        return documented, missing

    @staticmethod
    def has_abstractmethod_decorator(
        node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> bool:
        """Return *True* if *node* has an ``@abstractmethod`` decorator."""
        return any(
            (isinstance(d, ast.Name) and d.id == "abstractmethod")
            or (isinstance(d, ast.Attribute) and d.attr == "abstractmethod")
            for d in node.decorator_list
        )

    @staticmethod
    def is_stub_body(
        node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> bool:
        """Return *True* if *node*'s body is just ``...`` or ``pass``."""
        if len(node.body) != 1:
            return False
        stmt = node.body[0]
        if isinstance(stmt, ast.Pass):
            return True
        return (
            isinstance(stmt, ast.Expr)
            and isinstance(stmt.value, ast.Constant)
            and stmt.value.value is ...
        )

    @staticmethod
    def is_abstract_stub(
        node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> bool:
        """Check if node is an abstract method stub (body is ``...`` or ``pass``)."""
        return DocstringCoverageRule.has_abstractmethod_decorator(
            node
        ) and DocstringCoverageRule.is_stub_body(node)

    @staticmethod
    def _is_setter_or_deleter(
        node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> bool:
        """Check if node is a property setter or deleter."""
        for dec in node.decorator_list:
            if isinstance(dec, ast.Attribute) and dec.attr in ("setter", "deleter"):
                return True
        return False

    @staticmethod
    def _build_class_map(
        tree: ast.Module,
    ) -> dict[str, ast.ClassDef]:
        """Build a name -> ClassDef map for all classes in the module."""
        return {
            node.name: node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
        }

    def _find_enclosing_class(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        class_map: dict[str, ast.ClassDef],
    ) -> ast.ClassDef | None:
        """Return the class whose body contains *node*, or None."""
        for cls in class_map.values():
            for item in cls.body:
                if item is node:
                    return cls
        return None

    def _resolve_base_class(
        self,
        base_name: str,
        class_map: dict[str, ast.ClassDef],
        global_classes: dict[str, list[ast.ClassDef]] | None,
    ) -> ast.ClassDef | None:
        """Resolve *base_name* to a ClassDef via same-file or cross-file lookup."""
        if base_name in class_map:
            return class_map[base_name]
        if global_classes and base_name in global_classes:
            definitions = global_classes[base_name]
            if len(definitions) == 1:
                return definitions[0]
        return None

    def _is_abstract_override(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        class_map: dict[str, ast.ClassDef],
        global_classes: dict[str, list[ast.ClassDef]] | None = None,
    ) -> bool:
        """Check if node overrides a documented abstractmethod."""
        enclosing = self._find_enclosing_class(node, class_map)
        if enclosing is None:
            return False

        for base in enclosing.bases:
            base_name = base.id if isinstance(base, ast.Name) else None
            if base_name is None:
                continue
            base_cls = self._resolve_base_class(base_name, class_map, global_classes)
            if base_cls is not None and self._check_abstract_parent(
                base_cls, node.name
            ):
                return True

        return False

    def _check_abstract_parent(
        self,
        base_cls: ast.ClassDef,
        method_name: str,
    ) -> bool:
        """Check if base_cls has a documented @abstractmethod named *method_name*."""
        for item in base_cls.body:
            if not isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            if item.name != method_name:
                continue
            if self.has_abstractmethod_decorator(item) and self._has_docstring(item):
                return True
        return False

    def _has_docstring(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
        """Check if a function node has a docstring."""
        if not node.body:
            return False
        first = node.body[0]
        return (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        )
