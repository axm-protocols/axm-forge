"""Duplication rule — AST-based copy-paste detection."""

from __future__ import annotations

import ast
import hashlib
import logging
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from axm_audit.core.rules._helpers import get_ast_cache as _get_ast_cache
from axm_audit.core.rules._helpers import get_python_files as _get_python_files
from axm_audit.core.rules._helpers import parse_file_safe as _parse_file_safe
from axm_audit.core.rules.base import ProjectRule, register_rule
from axm_audit.models.results import CheckResult, Severity

logger = logging.getLogger(__name__)

__all__ = ["DuplicationRule"]

# Minimum lines for a function body to be considered for duplication
_MIN_DUP_LINES = 6

# A group must have at least this many identical entries to be a clone
_MIN_CLONE_GROUP = 2


def _normalize_ast(node: ast.AST) -> str:
    """Produce a canonical string from an AST subtree.

    Strips names, line numbers, and columns so that structurally
    identical code with different variable names is considered equal.
    """
    return ast.dump(node, annotate_fields=False, include_attributes=False)


@dataclass
@register_rule("architecture")
class DuplicationRule(ProjectRule):
    """Detect copy-pasted code via AST structure hashing.

    Extracts function and method bodies, normalises them by stripping
    variable names and locations, hashes each body, and reports
    groups whose hash appears more than once.

    Scoring: ``100 - (dup_groups * 10)``, min 0.
    """

    min_lines: int = _MIN_DUP_LINES

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule."""
        return "ARCH_DUPLICATION"

    def check(self, project_path: Path) -> CheckResult:
        """Check for code duplication in the project."""
        early = self.check_src(project_path)
        if early is not None:
            return early

        src_path = project_path / "src"

        clones = self._find_duplicates(src_path)
        dup_count = len(clones)
        score = max(0, 100 - dup_count * 10)
        passed = dup_count == 0

        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=f"{dup_count} duplicate block(s) found",
            severity=Severity.WARNING if not passed else Severity.INFO,
            details={"dup_count": dup_count, "clones": clones[:20], "score": score},
            fix_hint=(
                "Extract duplicated code into shared functions" if not passed else None
            ),
        )

    def _find_duplicates(self, src_path: Path) -> list[dict[str, str]]:
        """Hash function bodies and find duplicates."""
        seen = self._collect_function_hashes(src_path)

        clones: list[dict[str, str]] = []
        for entries in seen.values():
            if len(entries) < _MIN_CLONE_GROUP:
                continue
            first = entries[0]
            for other in entries[1:]:
                clones.append(
                    {
                        "source": f"{first[0]}:{first[1]}:{first[2]}",
                        "target": f"{other[0]}:{other[1]}:{other[2]}",
                    }
                )
        return clones

    def _collect_function_hashes(
        self,
        src_path: Path,
    ) -> dict[str, list[tuple[str, str, int]]]:
        """Scan source files and hash each function body."""
        seen: dict[str, list[tuple[str, str, int]]] = defaultdict(list)

        for path in _get_python_files(src_path):
            _cache = _get_ast_cache()
            tree = _cache.get_or_parse(path) if _cache else _parse_file_safe(path)
            if tree is None:
                continue
            rel = str(path.relative_to(src_path))
            self._hash_functions_in_tree(tree, rel, seen)

        return seen

    def _hash_functions_in_tree(
        self,
        tree: ast.Module,
        rel: str,
        seen: dict[str, list[tuple[str, str, int]]],
    ) -> None:
        """Hash each function body in a single AST and add to *seen*."""
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            end = getattr(node, "end_lineno", None) or node.lineno
            if end - node.lineno + 1 < self.min_lines:
                continue
            body_str = _normalize_ast(node)
            h = hashlib.md5(body_str.encode(), usedforsecurity=False).hexdigest()
            seen[h].append((rel, node.name, node.lineno))
