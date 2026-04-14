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

        # Group missing functions by file for text rendering
        text: str | None = None
        if missing:
            groups: dict[str, list[str]] = {}
            for item in missing:
                file_part, _, func_name = item.rpartition(":")
                groups.setdefault(file_part, []).append(func_name)
            text_lines = [
                f"     \u2022 {path}: {', '.join(funcs)}"
                for path, funcs in groups.items()
            ]
            text = "\n".join(text_lines)

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
            text=text,
            fix_hint="Add docstrings to public functions" if missing else None,
        )

    def _analyze_docstrings(self, src_path: Path) -> tuple[int, list[str]]:
        """Analyze docstring coverage in source files.

        Returns:
            Tuple of (documented_count, list of missing function locations).
        """
        documented = 0
        missing: list[str] = []

        # Pre-pass: parse all files and build package-wide class registry
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
            if self._is_abstract_stub(node):
                continue
            if self._is_abstract_override(node, class_map, global_classes):
                continue

            if self._has_docstring(node):
                documented += 1
            else:
                missing.append(f"{rel_path}:{node.name}")
        return documented, missing

    @staticmethod
    def _has_abstractmethod_decorator(
        node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> bool:
        """Return *True* if *node* has an ``@abstractmethod`` decorator."""
        return any(
            (isinstance(d, ast.Name) and d.id == "abstractmethod")
            or (isinstance(d, ast.Attribute) and d.attr == "abstractmethod")
            for d in node.decorator_list
        )

    @staticmethod
    def _is_stub_body(
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
    def _is_abstract_stub(
        node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> bool:
        """Check if node is an abstract method stub (body is ``...`` or ``pass``)."""
        return DocstringCoverageRule._has_abstractmethod_decorator(
            node
        ) and DocstringCoverageRule._is_stub_body(node)

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
            if self._has_abstractmethod_decorator(item) and self._has_docstring(item):
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


@dataclass
@register_rule("practices")
class BareExceptRule(ProjectRule):
    """Detect bare except clauses (except: without type)."""

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule."""
        return "PRACTICE_BARE_EXCEPT"

    def check(self, project_path: Path) -> CheckResult:
        """Check for bare except clauses in the project.

        Returns a ``CheckResult`` with ``text`` containing one bullet per
        location (shortened to the last two path parts) when bare excepts
        are found, or ``None`` when the project passes.
        """
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

        _min_depth = 2
        text_lines = []
        for loc in bare_excepts:
            file_path = Path(str(loc["file"]))
            short = (
                "/".join(file_path.parts[-_min_depth:])
                if len(file_path.parts) > _min_depth
                else file_path.parts[-1]
            )
            text_lines.append(f"     \u2022 {short}:{loc['line']}")

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
            text="\n".join(text_lines) if text_lines else None,
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

        text_lines = [
            f"     \u2022 {m['file']}:{m['line']} {m['pattern']}" for m in matches
        ]

        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=f"{count} potential secret(s) found",
            severity=Severity.ERROR if not passed else Severity.INFO,
            details={"secret_count": count, "matches": matches, "score": score},
            text="\n".join(text_lines) if text_lines else None,
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

        text_lines = [
            f"     \u2022 {v['file']}:{v['line']}: {v['issue']}" for v in violations
        ]

        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=f"{count} blocking-IO violation(s) found",
            severity=Severity.WARNING if not passed else Severity.INFO,
            details={"violations": violations, "score": score},
            text="\n".join(text_lines) if text_lines else None,
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


# ── Test mirror ───────────────────────────────────────────────────────

# Files exempt from the 1:1 test requirement
_TEST_MIRROR_EXEMPT = {"__init__.py", "_version.py", "conftest.py", "py.typed"}


@dataclass
@register_rule("practices")
class TestMirrorRule(ProjectRule):
    """Check that every source module has a corresponding test file.

    For each ``src/<pkg>/foo.py``, looks for ``tests/**/test_foo.py``
    anywhere in the test tree (supports flat and nested layouts).

    Private modules (leading underscores) are matched with the prefix
    stripped: ``_facade.py`` matches ``test_facade.py`` or
    ``test__facade.py``.

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

        missing: list[str] = []
        for name in sorted(set(source_modules)):
            stripped = name.lstrip("_")
            candidates = {f"test_{stripped}", f"test_{name}"}
            if not candidates & test_basenames:
                missing.append(name)
        return missing
