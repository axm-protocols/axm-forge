"""Practice rules — code quality patterns via AST and regex."""

from __future__ import annotations

import ast
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from axm_audit.core.rules._helpers import (
    get_ast_cache,
    get_python_files,
    parse_file_safe,
)
from axm_audit.core.rules.base import ProjectRule, register_rule
from axm_audit.models.results import CheckResult, Severity

logger = logging.getLogger(__name__)

# HTTP libraries whose calls should have a timeout= kwarg
_HTTP_LIBRARIES = {"requests", "httpx"}
_HTTP_METHODS = {"get", "post", "put", "delete", "patch", "head", "options"}


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

    def _analyze_docstrings(self, src_path: Path) -> tuple[int, list[str]]:
        """Analyze docstring coverage in source files.

        Returns:
            Tuple of (documented_count, list of missing function locations).
        """
        documented = 0
        missing: list[str] = []

        for path in get_python_files(src_path):
            cache = get_ast_cache()
            tree = cache.get_or_parse(path) if cache else parse_file_safe(path)
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

        bare_excepts: list[dict[str, str | int]] = []
        py_files = get_python_files(src_path)

        for path in py_files:
            cache = get_ast_cache()
            tree = cache.get_or_parse(path) if cache else parse_file_safe(path)
            if tree is None:
                continue

            self._find_bare_excepts(tree, path, src_path, bare_excepts)

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
                # type is None means bare except:
                if node.type is None:
                    bare_excepts.append(
                        {
                            "file": str(path.relative_to(src_path)),
                            "line": node.lineno,
                        }
                    )


@dataclass
@register_rule("security")
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
        early = self.check_src(project_path)
        if early is not None:
            return early

        src_path = project_path / "src"

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
@register_rule("practices")
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
    """Determine whether an AST call target belongs to an HTTP library.

    Recognises three patterns:
    - Direct: ``requests.get(...)`` / ``httpx.post(...)``
    - Chained client: ``httpx.AsyncClient().get(...)``
    - Attribute chain: ``httpx.something.get(...)``
    """
    return (
        _is_direct_http_name(value)
        or _is_chained_client_call(value)
        or _is_http_attribute_chain(value)
    )


@dataclass
@register_rule("practices")
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
        early = self.check_src(project_path)
        if early is not None:
            return early

        src_path = project_path / "src"

        without_logging, total_checked = self._scan_logging_coverage(src_path)

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

    def _should_check_module(
        self,
        path: Path,
        tree: ast.Module,
    ) -> bool:
        """Determine if a module is substantial enough to require logging."""
        if path.name in {"__init__.py", "_version.py"}:
            return False
        top_defs = sum(
            1
            for node in ast.iter_child_nodes(tree)
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
        )
        return top_defs >= self.min_defs

    def _scan_logging_coverage(
        self,
        src_path: Path,
    ) -> tuple[list[str], int]:
        """Scan modules and return (without_logging, total_checked)."""
        without_logging: list[str] = []
        total_checked = 0

        for path in get_python_files(src_path):
            cache = get_ast_cache()
            tree = cache.get_or_parse(path) if cache else parse_file_safe(path)
            if tree is None:
                continue
            if not self._should_check_module(path, tree):
                continue

            total_checked += 1
            if not self._has_logging_import(tree):
                without_logging.append(str(path.relative_to(src_path)))

        return without_logging, total_checked

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


# ── Test mirror ───────────────────────────────────────────────────────

# Files exempt from the 1:1 test requirement
_TEST_MIRROR_EXEMPT = {"__init__.py", "_version.py", "conftest.py", "py.typed"}


@dataclass
@register_rule("practices")
class TestMirrorRule(ProjectRule):
    """Check that every source module has a corresponding test file.

    For each ``src/<pkg>/foo.py``, looks for ``tests/**/test_foo.py``
    anywhere in the test tree (supports flat and nested layouts).

    Scoring: 100 - (missing_count * 15), min 0.
    """

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule."""
        return "PRACTICE_TEST_MIRROR"

    def check(self, project_path: Path) -> CheckResult:
        """Check test file coverage for source modules."""
        early = self.check_src(project_path)
        if early is not None:
            return early

        src_path = project_path / "src"

        tests_path = project_path / "tests"
        missing = self._find_untested_modules(src_path, tests_path)

        if not missing:
            return CheckResult(
                rule_id=self.rule_id,
                passed=True,
                message="All source modules have test files",
                severity=Severity.INFO,
            )

        score = max(0, 100 - len(missing) * 15)
        passed = score >= 90  # noqa: PLR2004

        hint_files = ", ".join(f"tests/test_{m}" for m in missing[:5])
        if len(missing) > 5:  # noqa: PLR2004
            hint_files += f" (+{len(missing) - 5} more)"

        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=f"{len(missing)} source module(s) without tests",
            severity=Severity.WARNING if not passed else Severity.INFO,
            details={"missing": missing, "score": score},
            fix_hint=f"Create test files: {hint_files}",
        )

    @staticmethod
    def _collect_source_modules(src_path: Path) -> list[str]:
        """Collect non-exempt Python module basenames from ``src/``."""
        pkg_dirs = [
            d for d in src_path.iterdir() if d.is_dir() and d.name != "__pycache__"
        ]
        modules: list[str] = []
        for pkg_dir in pkg_dirs:
            for py_file in pkg_dir.rglob("*.py"):
                if py_file.name not in _TEST_MIRROR_EXEMPT:
                    modules.append(py_file.name)
        return modules

    @staticmethod
    def _collect_test_basenames(tests_path: Path) -> set[str]:
        """Collect all ``test_*.py`` basenames from the test tree."""
        if not tests_path.exists():
            return set()
        return {f.name for f in tests_path.rglob("test_*.py")}

    @classmethod
    def _find_untested_modules(
        cls,
        src_path: Path,
        tests_path: Path,
    ) -> list[str]:
        """Find source modules without corresponding test files.

        Args:
            src_path: The ``src/`` directory.
            tests_path: The ``tests/`` directory.

        Returns:
            List of module basenames (e.g. ``["foo.py", "bar.py"]``)
            that have no matching ``test_*.py`` file.
        """
        source_modules = cls._collect_source_modules(src_path)
        if not source_modules:
            return []

        test_basenames = cls._collect_test_basenames(tests_path)

        return [
            name
            for name in sorted(set(source_modules))
            if f"test_{name}" not in test_basenames
        ]
