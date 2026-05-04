"""Bare except clause detection."""

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

__all__ = ["BareExceptRule"]


def _short_path(file_str: str, depth: int = 2) -> str:
    """Shorten *file_str* to the last *depth* path parts."""
    parts = Path(file_str).parts
    if len(parts) > depth:
        return "/".join(parts[-depth:])
    return parts[-1]


@dataclass
@register_rule("practices")
class BareExceptRule(ProjectRule):
    """Detect bare except clauses (except: without type)."""

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule."""
        return "PRACTICE_BARE_EXCEPT"

    def check(self, project_path: Path) -> CheckResult:
        """Check for bare except clauses in the project."""
        early = self.check_src(project_path)
        if early is not None:
            return early

        src_path = project_path / "src"
        bare_excepts = self._collect_bare_excepts(src_path)

        count = len(bare_excepts)
        passed = count == 0
        score = max(0, 100 - count * 20)

        text_lines = [
            f"     • {_short_path(str(loc['file']))}:{loc['line']}"
            for loc in bare_excepts
        ]

        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=f"{count} bare except(s) found",
            severity=Severity.WARNING if not passed else Severity.INFO,
            score=int(score),
            details={
                "bare_except_count": count,
                "locations": bare_excepts,
            },
            text="\n".join(text_lines) if text_lines else None,
            fix_hint="Use specific exception types (e.g., except ValueError:)"
            if not passed
            else None,
        )

    def _collect_bare_excepts(
        self,
        src_path: Path,
    ) -> list[dict[str, str | int]]:
        """Parse every ``.py`` file under *src_path* and gather bare excepts."""
        bare_excepts: list[dict[str, str | int]] = []
        for path in get_python_files(src_path):
            cache = get_ast_cache()
            tree = cache.get_or_parse(path) if cache else parse_file_safe(path)
            if tree is None:
                continue
            self._find_bare_excepts(tree, path, src_path, bare_excepts)
        return bare_excepts

    def _find_bare_excepts(
        self,
        tree: ast.Module,
        path: Path,
        src_path: Path,
        bare_excepts: list[dict[str, str | int]],
    ) -> None:
        """Find bare except clauses in a syntax tree."""
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                if node.type is None:
                    bare_excepts.append(
                        {
                            "file": str(path.relative_to(src_path)),
                            "line": node.lineno,
                        }
                    )
