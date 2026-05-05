"""Flag tests that reach into private (``_prefixed``) package symbols.

Tests that import ``_private`` helpers couple the suite to implementation
details, turning refactors into multi-file chores.  The rule walks every
``tests/**/test_*.py`` file, collects imports of underscore-prefixed
symbols from first-party packages and classifies each hit via
``axm_ast.extract_module_info``.

Beyond ``from pkg import _foo`` aliases, the rule also flags attribute
access on first-party imports — e.g. ``Cls._method()`` after
``from pkg.mod import Cls``, or ``mod._var`` after ``import pkg.mod as mod``.

Dunders (``__version__``) are always ignored and ``_UPPER_CASE`` constants
are ignored by default — flip ``include_constants=True`` on the rule
instance to surface those as well.  Namedtuple methods (``_asdict``,
``_replace`` …) are always ignored.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from axm_ast import ModuleInfo
from axm_ast.core.parser import extract_module_info

from axm_audit.core.rules.base import ProjectRule, register_rule
from axm_audit.core.rules.test_quality._shared import (
    get_pkg_prefixes,
    iter_test_files,
)
from axm_audit.models.results import CheckResult, Severity

__all__ = ["PrivateImportsRule"]


_DUNDER_RE = re.compile(r"^__\w+__$")
_CONSTANT_RE = re.compile(r"^_[A-Z][A-Z0-9_]+$")
_DOCS_ANCHOR = "docs/test_quality.md#private-imports"
_SCORE_PENALTY = 5
_MAX_TEXT_ITEMS = 20
_NAMEDTUPLE_API: frozenset[str] = frozenset(
    {"_asdict", "_replace", "_fields", "_make", "_field_defaults", "_source"}
)


def _relativize(path: str, project_path: Path) -> str:
    """Return ``path`` relative to ``project_path`` when possible."""
    try:
        return str(Path(path).relative_to(project_path))
    except ValueError:
        return path


def _render_private_imports_text(
    findings: list[dict[str, Any]], project_path: Path
) -> str:
    """Render top-N private-import findings as a compact bullet list."""
    lines = [
        f"• [{f.get('access_kind', 'import')}] "
        f"{_relativize(f['test_file'], project_path)}:{f['line']} "
        f"{f['import_module']}.{f['private_symbol']} ({f['symbol_kind']})"
        for f in findings[:_MAX_TEXT_ITEMS]
    ]
    if len(findings) > _MAX_TEXT_ITEMS:
        lines.append(f"(+{len(findings) - _MAX_TEXT_ITEMS} more)")
    return "\n".join(lines)


@dataclass(frozen=True)
class _ScanContext:
    project_path: Path
    pkg_prefixes: list[str]
    mod_cache: dict[str, ModuleInfo | None]
    include_constants: bool = False


def _variable_kind(name: str) -> str:
    return "constant" if _CONSTANT_RE.match(name) else "variable"


def _is_private_symbol(name: str, include_constants: bool) -> bool:
    if not name.startswith("_"):
        return False
    if _DUNDER_RE.match(name):
        return False
    if _CONSTANT_RE.match(name) and not include_constants:
        return False
    return True


def _is_first_party_module(mod: str, pkg_prefixes: Iterable[str]) -> bool:
    return any(mod == p or mod.startswith(p + ".") for p in pkg_prefixes)


def _iter_private_aliases(
    node: ast.ImportFrom,
    ctx: _ScanContext,
    test_pkg: str | None,
) -> Iterator[tuple[str, str]]:
    if not node.module:
        return
    mod = node.module
    if not _is_first_party_module(mod, ctx.pkg_prefixes):
        return
    for alias in node.names or []:
        name = alias.name
        if not _is_private_symbol(name, ctx.include_constants):
            continue
        if _is_same_package_module_import(mod, name, ctx.project_path, test_pkg):
            continue
        yield mod, name


@dataclass(frozen=True)
class _FindingSpec:
    test_file: Path
    line: int
    mod: str
    name: str
    kind: str
    access_kind: str = "import"


def _build_finding(spec: _FindingSpec) -> dict[str, Any]:
    return {
        "test_file": str(spec.test_file),
        "line": spec.line,
        "import_module": spec.mod,
        "private_symbol": spec.name,
        "symbol_kind": spec.kind,
        "access_kind": spec.access_kind,
    }


def _test_owning_package(
    test_file: Path, project_path: Path, pkg_prefixes: Iterable[str]
) -> str | None:
    """Return the top-level first-party package the test belongs to.

    For single-package projects, every test belongs to that package.  For
    multi-package projects, the owning package is inferred from the test
    path under ``tests/`` (e.g. ``tests/pkg_b/test_x.py`` -> ``pkg_b``).
    Returns ``None`` when the owner cannot be determined.
    """
    prefixes = set(pkg_prefixes)
    if len(prefixes) == 1:
        return next(iter(prefixes))
    try:
        rel = test_file.relative_to(project_path / "tests")
    except ValueError:
        return None
    for part in rel.parts:
        if part in prefixes:
            return part
    return None


def _is_same_package_module_import(
    module: str, name: str, project_path: Path, test_pkg: str | None
) -> bool:
    """True when ``from module import name`` targets a private *submodule*
    that lives in the same top-level package as the importing test file.
    """
    if test_pkg is None or module.split(".", 1)[0] != test_pkg:
        return False
    rel = (module + "." + name).replace(".", "/")
    src = project_path / "src"
    return (src / f"{rel}.py").exists() or (src / rel / "__init__.py").exists()


# Attribute-access detection helpers


def _collect_from_imports(
    node: ast.ImportFrom,
    ctx: _ScanContext,
    out: dict[str, tuple[str, str, str]],
) -> None:
    """Record ``from pkg.mod import Name [as N]`` bindings into ``out``."""
    mod = node.module or ""
    if not mod or not _is_first_party_module(mod, ctx.pkg_prefixes):
        return
    for alias in node.names or []:
        if alias.name == "*":
            continue
        local = alias.asname or alias.name
        out[local] = (mod, "symbol", alias.name)


def _collect_plain_imports(
    node: ast.Import,
    ctx: _ScanContext,
    out: dict[str, tuple[str, str, str]],
) -> None:
    """Record ``import pkg.mod [as m]`` bindings into ``out``."""
    for alias in node.names:
        mod = alias.name
        if not _is_first_party_module(mod, ctx.pkg_prefixes):
            continue
        if alias.asname:
            out[alias.asname] = (mod, "module", mod)
        else:
            root = mod.split(".", 1)[0]
            out.setdefault(root, (root, "module", root))
            out[mod] = (mod, "module", mod)


def _collect_first_party_imports(
    tree: ast.AST, ctx: _ScanContext
) -> dict[str, tuple[str, str, str]]:
    """Map each local name to ``(module, kind, original)`` for first-party imports.

    ``kind`` is ``"symbol"`` for ``from pkg.mod import Name`` (Name binds a
    symbol from ``pkg.mod``) and ``"module"`` for ``import pkg.mod`` /
    ``import pkg.mod as m`` (the local name binds the module itself).
    ``original`` is the original symbol name (pre-asname) for ``"symbol"``,
    or the dotted module path for ``"module"``.
    """
    out: dict[str, tuple[str, str, str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            _collect_from_imports(node, ctx, out)
        elif isinstance(node, ast.Import):
            _collect_plain_imports(node, ctx, out)
    return out


def _attribute_dotted_prefix(node: ast.Attribute) -> str | None:
    """Return the dotted prefix from ``a.b.c._attr`` (excluding the trailing attr)."""
    parts: list[str] = []
    cur: ast.AST = node.value
    while isinstance(cur, ast.Attribute):
        parts.insert(0, cur.attr)
        cur = cur.value
    if not isinstance(cur, ast.Name):
        return None
    parts.insert(0, cur.id)
    return ".".join(parts)


def _resolve_attr_target(
    node: ast.Attribute, imports_map: dict[str, tuple[str, str, str]]
) -> tuple[str, str | None] | None:
    """Resolve ``X._attr`` to ``(module, class_name | None)``.

    Returns ``None`` when the root binding is not a first-party import.
    For ``Cls._m`` after ``from pkg.mod import Cls`` (or ``as C``), returns
    ``("pkg.mod", "Cls")``. For ``mod._var`` after
    ``import pkg.mod as mod`` returns ``("pkg.mod", None)``.
    For ``mod.Cls._method`` returns ``("pkg.mod", "Cls")``.
    """
    prefix = _attribute_dotted_prefix(node)
    if prefix is None:
        return None
    if prefix in imports_map:
        mod, kind, original = imports_map[prefix]
        return (mod, None) if kind == "module" else (mod, original)
    root = prefix.split(".", 1)[0]
    binding = imports_map.get(root)
    if binding is None:
        return None
    mod, kind, original = binding
    if kind == "symbol":
        return (mod, original)
    rest = prefix[len(root) + 1 :] if "." in prefix else ""
    head = rest.split(".", 1)[0] if rest else None
    return (mod, head)


def _iter_private_attributes(
    tree: ast.AST,
    ctx: _ScanContext,
    imports_map: dict[str, tuple[str, str, str]],
) -> Iterator[tuple[str, str | None, str, ast.Attribute]]:
    """Yield ``(module, class_name, attr_name, node)`` for private attribute access.

    Skips dunder access, namedtuple API, and constants when
    ``ctx.include_constants`` is False.
    """
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute):
            continue
        attr = node.attr
        if attr in _NAMEDTUPLE_API:
            continue
        if not _is_private_symbol(attr, ctx.include_constants):
            continue
        target = _resolve_attr_target(node, imports_map)
        if target is None:
            continue
        module, class_name = target
        yield module, class_name, attr, node


@dataclass
@register_rule("test_quality")
class PrivateImportsRule(ProjectRule):
    """Report test imports of private package symbols."""

    include_constants: bool = False

    @property
    def rule_id(self) -> str:
        """Stable identifier for this rule."""
        return "TEST_QUALITY_PRIVATE_IMPORTS"

    def check(self, project_path: Path) -> CheckResult:
        """Scan test files in ``project_path`` for private-symbol imports.

        Walks every ``tests/**/test_*.py`` file under ``project_path``,
        collects ``ImportFrom`` nodes that reference first-party packages
        and flags each underscore-prefixed alias.  Dunders are always
        ignored; ``_UPPER_CASE`` constants are ignored unless
        ``include_constants`` is ``True``.

        Returns a :class:`CheckResult` with ``passed=True`` when no
        private imports are found.  Otherwise ``details["findings"]``
        lists each offending import (test file, line, source module,
        symbol, and resolved kind) and ``score`` reports a
        100-point score penalised by ``_SCORE_PENALTY`` per finding.
        """
        early = self.check_src(project_path)
        if early is not None:
            return early

        pkg_prefixes = get_pkg_prefixes(project_path)
        findings: list[dict[str, Any]] = []
        mod_cache: dict[str, ModuleInfo | None] = {}

        ctx = _ScanContext(
            project_path=project_path,
            pkg_prefixes=list(pkg_prefixes),
            mod_cache=mod_cache,
            include_constants=self.include_constants,
        )
        for test_file, tree in iter_test_files(project_path):
            if tree is None:
                continue
            test_pkg = _test_owning_package(test_file, project_path, ctx.pkg_prefixes)
            findings.extend(
                self._scan_file_for_private_imports(test_file, tree, ctx, test_pkg)
            )

        return self._build_check_result(findings, project_path)

    def _scan_file_for_private_imports(
        self,
        test_file: Path,
        tree: ast.AST,
        ctx: _ScanContext,
        test_pkg: str | None = None,
    ) -> list[dict[str, Any]]:
        """Walk *tree* and return one finding per private-symbol access."""
        findings: list[dict[str, Any]] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            for mod, name in _iter_private_aliases(node, ctx, test_pkg):
                kind = self._resolve_symbol_kind(
                    mod, name, ctx.project_path, ctx.mod_cache
                )
                findings.append(
                    _build_finding(
                        _FindingSpec(
                            test_file=test_file,
                            line=node.lineno,
                            mod=mod,
                            name=name,
                            kind=kind,
                            access_kind="import",
                        )
                    )
                )

        imports_map = _collect_first_party_imports(tree, ctx)
        for mod, class_name, attr, attr_node in _iter_private_attributes(
            tree, ctx, imports_map
        ):
            kind = self._resolve_attr_kind(mod, class_name, attr, ctx)
            if kind == "unknown":
                continue
            findings.append(
                _build_finding(
                    _FindingSpec(
                        test_file=test_file,
                        line=attr_node.lineno,
                        mod=mod,
                        name=attr,
                        kind=kind,
                        access_kind="attribute",
                    )
                )
            )
        return findings

    def _build_check_result(
        self, findings: list[dict[str, Any]], project_path: Path
    ) -> CheckResult:
        n = len(findings)
        score = max(0, 100 - n * _SCORE_PENALTY)
        passed = n == 0
        if passed:
            message = f"No private imports in tests/ (see {_DOCS_ANCHOR})"
        else:
            message = f"{n} private import(s) in tests/ — see {_DOCS_ANCHOR}"
        text = (
            _render_private_imports_text(findings, project_path) if findings else None
        )
        fix_hint = (
            None
            if passed
            else "Re-export the symbol publicly or test via the public API"
        )
        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=message,
            severity=Severity.ERROR,
            score=int(score),
            details={"findings": findings},
            text=text,
            fix_hint=fix_hint,
        )

    def _resolve_symbol_kind(
        self,
        module: str,
        symbol: str,
        pkg_root: Path,
        cache: dict[str, ModuleInfo | None],
    ) -> str:
        """Return the kind of *symbol* in *module*.

        Possible values: function, class, constant, variable, unknown.
        """
        if module not in cache:
            cache[module] = self._load_module_info(module, pkg_root)
        info = cache[module]
        if info is None:
            return "unknown"
        return self._lookup_symbol_in_info(info, symbol)

    def _resolve_attr_kind(
        self,
        module: str,
        class_name: str | None,
        attr: str,
        ctx: _ScanContext,
    ) -> str:
        """Resolve ``attr`` against ``module`` (optionally scoped to a class).

        For ``class_name=None`` (module-level access), reuses
        :meth:`_resolve_symbol_kind`. For ``class_name=Cls``, the name may
        also reference a submodule of *module* (``from pkg import _sub``);
        when ``pkg/_sub.py`` exists, treat as module access. Otherwise look
        up ``attr`` on the class's methods.
        """
        if class_name is not None:
            sub = f"{module}.{class_name}"
            sub_info = self._load_module_info(sub, ctx.project_path)
            if sub_info is not None:
                ctx.mod_cache.setdefault(sub, sub_info)
                return self._lookup_symbol_in_info(sub_info, attr)
        if module not in ctx.mod_cache:
            ctx.mod_cache[module] = self._load_module_info(module, ctx.project_path)
        info = ctx.mod_cache[module]
        if info is None:
            return "unknown"
        if class_name is not None:
            if _class_has_member(info, class_name, attr):
                return "method"
            return "unknown"
        return self._lookup_symbol_in_info(info, attr)

    @staticmethod
    def _lookup_symbol_in_info(info: ModuleInfo, symbol: str) -> str:
        dispatch: list[tuple[list[Any], str | Callable[[str], str]]] = [
            (info.functions, "function"),
            (info.classes, "class"),
            (info.variables, _variable_kind),
        ]
        for entries, kind in dispatch:
            for entry in entries:
                if entry.name == symbol:
                    return kind(symbol) if callable(kind) else kind
        return "unknown"

    def _load_module_info(self, module: str, pkg_root: Path) -> ModuleInfo | None:
        path = self._resolve_source_path(module, pkg_root)
        if path is None:
            return None
        try:
            return extract_module_info(path)
        except (FileNotFoundError, ValueError, OSError):
            return None

    @staticmethod
    def _resolve_source_path(module: str, pkg_root: Path) -> Path | None:
        rel = module.replace(".", "/")
        candidates = (
            pkg_root / "src" / f"{rel}.py",
            pkg_root / "src" / rel / "__init__.py",
        )
        for cand in candidates:
            if cand.exists():
                return cand
        return None


def _class_has_member(info: ModuleInfo, class_name: str, member: str) -> bool:
    """True when *class_name* exists in *info* and exposes *member* as a
    method or a class-body variable assignment."""
    for cls in info.classes:
        if cls.name != class_name:
            continue
        for method in getattr(cls, "methods", []) or []:
            if method.name == member:
                return True
        return _class_has_var(info.path, class_name, member)
    return False


def _class_has_var(module_path: Path, class_name: str, name: str) -> bool:
    """True when *class_name* in *module_path* defines *name* via assignment."""
    try:
        tree = ast.parse(module_path.read_text(), filename=str(module_path))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return False
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef) or node.name != class_name:
            continue
        for stmt in node.body:
            if isinstance(stmt, ast.Assign):
                for target in stmt.targets:
                    if isinstance(target, ast.Name) and target.id == name:
                        return True
            elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                if stmt.target.id == name:
                    return True
    return False
