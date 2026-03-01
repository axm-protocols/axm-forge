"""Practice rules — code quality patterns via AST and regex."""

from __future__ import annotations

import ast
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from axm_audit.core.rules._helpers import get_python_files, parse_file_safe
from axm_audit.core.rules.base import ProjectRule
from axm_audit.models.results import CheckResult, Severity

logger = logging.getLogger(__name__)

# HTTP libraries whose calls should have a timeout= kwarg
_HTTP_LIBRARIES = {"requests", "httpx"}
_HTTP_METHODS = {"get", "post", "put", "delete", "patch", "head", "options"}


@dataclass
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
        src_path = project_path / "src"
        if not src_path.exists():
            return self._empty_result()

        documented, missing = self._analyze_docstrings(src_path)
        total = documented + len(missing)
        coverage = documented / total if total > 0 else 1.0
        passed = coverage >= self.min_coverage
        score = int(coverage * 100)

        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=f"Docstring coverage: {coverage:.0%} ({documented}/{total})",
            severity=Severity.WARNING if not passed else Severity.INFO,
            details={
                "coverage": round(coverage, 2),
                "total": total,
                "documented": documented,
                "missing": missing,
                "score": score,
            },
            fix_hint="Add docstrings to public functions" if missing else None,
        )

    def _empty_result(self) -> CheckResult:
        """Return result when src/ doesn't exist."""
        return CheckResult(
            rule_id=self.rule_id,
            passed=True,
            message="src/ directory not found",
            severity=Severity.INFO,
            details={"coverage": 1.0, "total": 0, "documented": 0, "missing": []},
        )

    def _analyze_docstrings(self, src_path: Path) -> tuple[int, list[str]]:
        """Analyze docstring coverage in source files.

        Returns:
            Tuple of (documented_count, list of missing function locations).
        """
        documented = 0
        missing: list[str] = []

        for path in get_python_files(src_path):
            tree = parse_file_safe(path)
            if tree is None:
                continue

            rel_path = path.relative_to(src_path)
            for node in ast.walk(tree):
                if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                    continue
                if node.name.startswith("_"):
                    continue

                if self._has_docstring(node):
                    documented += 1
                else:
                    missing.append(f"{rel_path}:{node.name}")

        return documented, missing

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


@dataclass
class BareExceptRule(ProjectRule):
    """Detect bare except clauses (except: without type)."""

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule."""
        return "PRACTICE_BARE_EXCEPT"

    def check(self, project_path: Path) -> CheckResult:
        """Check for bare except clauses in the project."""
        src_path = project_path / "src"
        if not src_path.exists():
            return CheckResult(
                rule_id=self.rule_id,
                passed=True,
                message="src/ directory not found",
                severity=Severity.INFO,
                details={"bare_except_count": 0, "locations": []},
            )

        bare_excepts: list[dict[str, str | int]] = []
        py_files = get_python_files(src_path)

        for path in py_files:
            tree = parse_file_safe(path)
            if tree is None:
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.ExceptHandler):
                    # type is None means bare except:
                    if node.type is None:
                        bare_excepts.append(
                            {
                                "file": str(path.relative_to(src_path)),
                                "line": node.lineno,
                            }
                        )

        count = len(bare_excepts)
        passed = count == 0
        score = max(0, 100 - count * 20)

        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=f"{count} bare except(s) found",
            severity=Severity.WARNING if not passed else Severity.INFO,
            details={
                "bare_except_count": count,
                "locations": bare_excepts,
                "score": score,
            },
            fix_hint="Use specific exception types (e.g., except ValueError:)"
            if not passed
            else None,
        )


@dataclass
class SecurityPatternRule(ProjectRule):
    """Detect hardcoded secrets via regex patterns."""

    patterns: list[str] = field(
        default_factory=lambda: [
            r"password\s*=\s*[\"'][^\"']+[\"']",
            r"secret\s*=\s*[\"'][^\"']+[\"']",
            r"api_key\s*=\s*[\"'][^\"']+[\"']",
            r"token\s*=\s*[\"'][^\"']+[\"']",
        ]
    )

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule."""
        return "PRACTICE_SECURITY"

    def check(self, project_path: Path) -> CheckResult:
        """Check for hardcoded secrets in the project."""
        src_path = project_path / "src"
        if not src_path.exists():
            return CheckResult(
                rule_id=self.rule_id,
                passed=True,
                message="src/ directory not found",
                severity=Severity.INFO,
                details={"secret_count": 0, "matches": []},
            )

        matches: list[dict[str, str | int]] = []
        py_files = get_python_files(src_path)

        for path in py_files:
            try:
                content = path.read_text()
            except (OSError, UnicodeDecodeError):
                continue

            for pattern in self.patterns:
                for match in re.finditer(pattern, content, re.IGNORECASE):
                    # Find line number
                    line_num = content[: match.start()].count("\n") + 1
                    matches.append(
                        {
                            "file": str(path.relative_to(src_path)),
                            "line": line_num,
                            "pattern": pattern.split(r"\s*")[0],  # Just the key name
                        }
                    )

        count = len(matches)
        passed = count == 0
        score = max(0, 100 - count * 25)

        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=f"{count} potential secret(s) found",
            severity=Severity.ERROR if not passed else Severity.INFO,
            details={"secret_count": count, "matches": matches, "score": score},
            fix_hint="Use environment variables or secret managers"
            if not passed
            else None,
        )


@dataclass
class BlockingIORule(ProjectRule):
    """Detect blocking I/O anti-patterns.

    Finds:
    - ``time.sleep()`` inside ``async def`` functions.
    - HTTP calls (``requests.*`` / ``httpx.*``) without ``timeout=`` kwarg.
    """

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule."""
        return "PRACTICE_BLOCKING_IO"

    def check(self, project_path: Path) -> CheckResult:
        """Check for blocking I/O patterns in the project."""
        src_path = project_path / "src"
        if not src_path.exists():
            return CheckResult(
                rule_id=self.rule_id,
                passed=True,
                message="src/ directory not found",
                severity=Severity.INFO,
                details={"violations": []},
            )

        violations: list[dict[str, str | int]] = []

        for path in get_python_files(src_path):
            tree = parse_file_safe(path)
            if tree is None:
                continue
            rel = str(path.relative_to(src_path))
            self._check_async_sleep(tree, rel, violations)
            self._check_http_no_timeout(tree, rel, violations)

        count = len(violations)
        passed = count == 0
        score = max(0, 100 - count * 15)

        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=f"{count} blocking-IO violation(s) found",
            severity=Severity.WARNING if not passed else Severity.INFO,
            details={"violations": violations, "score": score},
            fix_hint=(
                "Use asyncio.sleep() instead of time.sleep() in async context; "
                "add timeout= to HTTP calls"
            )
            if not passed
            else None,
        )

    # -- private helpers -------------------------------------------------------

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


def _is_http_call(value: ast.expr) -> bool:
    """Determine whether an AST call target belongs to an HTTP library.

    Recognises three patterns:
    - Direct: ``requests.get(...)`` / ``httpx.post(...)``
    - Chained client: ``httpx.AsyncClient().get(...)``
    - Attribute chain: ``httpx.something.get(...)``
    """
    # Direct call: requests.get(...)
    if isinstance(value, ast.Name) and value.id in _HTTP_LIBRARIES:
        return True

    # Chained call: httpx.AsyncClient().get(...)
    if isinstance(value, ast.Call):
        func = value.func
        if (
            isinstance(func, ast.Attribute)
            and func.attr in {"Client", "AsyncClient"}
            and isinstance(func.value, ast.Name)
            and func.value.id in _HTTP_LIBRARIES
        ):
            return True

    # Attribute chain: httpx.something.get(...)
    if isinstance(value, ast.Attribute):
        inner: ast.expr = value
        while isinstance(inner, ast.Attribute):
            inner = inner.value
        if isinstance(inner, ast.Name) and inner.id in _HTTP_LIBRARIES:
            return True

    return False


@dataclass
class LoggingPresenceRule(ProjectRule):
    """Verify that substantial source modules import logging.

    Exempts ``__init__.py``, ``_version.py``, and modules with fewer
    than 5 top-level definitions (functions + classes).
    """

    min_defs: int = 5

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule."""
        return "PRACTICE_LOGGING"

    def check(self, project_path: Path) -> CheckResult:
        """Check logging presence in source modules."""
        src_path = project_path / "src"
        if not src_path.exists():
            return CheckResult(
                rule_id=self.rule_id,
                passed=True,
                message="src/ directory not found",
                severity=Severity.INFO,
                details={"without_logging": []},
            )

        without_logging: list[str] = []
        total_checked = 0

        for path in get_python_files(src_path):
            rel = str(path.relative_to(src_path))

            # Exempt special files
            if path.name in {"__init__.py", "_version.py"}:
                continue

            tree = parse_file_safe(path)
            if tree is None:
                continue

            # Count top-level definitions
            top_defs = sum(
                1
                for node in ast.iter_child_nodes(tree)
                if isinstance(
                    node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef
                )
            )
            if top_defs < self.min_defs:
                continue

            total_checked += 1

            if not self._has_logging_import(tree):
                without_logging.append(rel)

        if total_checked == 0:
            return CheckResult(
                rule_id=self.rule_id,
                passed=True,
                message="No substantial modules to check",
                severity=Severity.INFO,
                details={"without_logging": [], "score": 100},
            )

        covered = total_checked - len(without_logging)
        coverage = covered / total_checked
        score = int(coverage * 100)
        passed = len(without_logging) == 0

        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=f"Logging coverage: {coverage:.0%} ({covered}/{total_checked})",
            severity=Severity.WARNING if not passed else Severity.INFO,
            details={"without_logging": without_logging, "score": score},
            fix_hint="Add import logging to modules" if not passed else None,
        )

    @staticmethod
    def _has_logging_import(tree: ast.Module) -> bool:
        """Check if the module imports ``logging`` or ``structlog``."""
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in {"logging", "structlog"}:
                        return True
            elif isinstance(node, ast.ImportFrom):
                if node.module in {"logging", "structlog"}:
                    return True
        return False
