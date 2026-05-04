"""Blocking I/O anti-pattern detection."""

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

__all__ = ["BlockingIORule"]

_HTTP_LIBRARIES = {"requests", "httpx"}
_HTTP_METHODS = {"get", "post", "put", "delete", "patch", "head", "options"}


def _is_direct_http_name(value: ast.expr) -> bool:
    """Match ``requests.get(...)`` — direct attribute on a library name."""
    return isinstance(value, ast.Name) and value.id in _HTTP_LIBRARIES


def _is_chained_client_call(value: ast.expr) -> bool:
    """Match ``httpx.AsyncClient().get(...)`` — constructor call chain."""
    if not isinstance(value, ast.Call):
        return False
    func = value.func
    return (
        isinstance(func, ast.Attribute)
        and func.attr in {"Client", "AsyncClient"}
        and isinstance(func.value, ast.Name)
        and func.value.id in _HTTP_LIBRARIES
    )


def _is_http_attribute_chain(value: ast.expr) -> bool:
    """Match ``httpx.something.get(...)`` — nested attribute access."""
    if not isinstance(value, ast.Attribute):
        return False
    inner: ast.expr = value
    while isinstance(inner, ast.Attribute):
        inner = inner.value
    return isinstance(inner, ast.Name) and inner.id in _HTTP_LIBRARIES


def _is_http_call(value: ast.expr) -> bool:
    """Determine whether an AST call target belongs to an HTTP library."""
    return (
        _is_direct_http_name(value)
        or _is_chained_client_call(value)
        or _is_http_attribute_chain(value)
    )


@dataclass
@register_rule("practices")
class BlockingIORule(ProjectRule):
    """Detect blocking I/O anti-patterns."""

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule."""
        return "PRACTICE_BLOCKING_IO"

    def check(self, project_path: Path) -> CheckResult:
        """Check for blocking I/O patterns in the project."""
        early = self.check_src(project_path)
        if early is not None:
            return early

        src_path = project_path / "src"

        violations: list[dict[str, str | int]] = []

        for path in get_python_files(src_path):
            cache = get_ast_cache()
            tree = cache.get_or_parse(path) if cache else parse_file_safe(path)
            if tree is None:
                continue
            rel = str(path.relative_to(src_path))
            self._check_async_sleep(tree, rel, violations)
            self._check_http_no_timeout(tree, rel, violations)

        count = len(violations)
        passed = count == 0
        score = max(0, 100 - count * 15)

        text_lines = [f"• {v['file']}:{v['line']}: {v['issue']}" for v in violations]

        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=f"{count} blocking-IO violation(s) found",
            severity=Severity.WARNING if not passed else Severity.INFO,
            score=int(score),
            details={"violations": violations},
            text="\n".join(text_lines) if text_lines else None,
            fix_hint=(
                "Use asyncio.sleep() instead of time.sleep() in async context; "
                "add timeout= to HTTP calls"
            )
            if not passed
            else None,
        )

    @staticmethod
    def _check_async_sleep(
        tree: ast.Module,
        rel: str,
        violations: list[dict[str, str | int]],
    ) -> None:
        """Find ``time.sleep()`` inside ``async def`` bodies."""
        for node in ast.walk(tree):
            if not isinstance(node, ast.AsyncFunctionDef):
                continue
            for child in ast.walk(node):
                if (
                    isinstance(child, ast.Call)
                    and isinstance(child.func, ast.Attribute)
                    and child.func.attr == "sleep"
                    and isinstance(child.func.value, ast.Name)
                    and child.func.value.id == "time"
                ):
                    violations.append(
                        {
                            "file": rel,
                            "line": child.lineno,
                            "issue": "time.sleep in async",
                        }
                    )

    @staticmethod
    def _check_http_no_timeout(
        tree: ast.Module,
        rel: str,
        violations: list[dict[str, str | int]],
    ) -> None:
        """Find HTTP calls without ``timeout=`` keyword argument."""
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in _HTTP_METHODS
            ):
                continue

            if not _is_http_call(node.func.value):
                continue

            has_timeout = any(kw.arg == "timeout" for kw in node.keywords)
            if not has_timeout:
                violations.append(
                    {
                        "file": rel,
                        "line": node.lineno,
                        "issue": "HTTP call without timeout",
                    }
                )
