"""Pyramid-level soft-signal rule — R1+R2+R3 core.

Classifies every ``tests/**/test_*.py`` function into ``unit`` /
``integration`` / ``e2e`` based on attr-IO, fixture arguments, taint of
``tmp_path``, and import provenance (public vs internal).  Mismatches
between the classified level and the folder the test lives in are
reported as findings.

R4 (conftest fixture-IO resolution) and R5 (mock neutralisation) are
stubbed here as identities — ticket #4b replaces the two placeholders.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, Field

from axm_audit.core.registry import register_rule
from axm_audit.core.rules.base import ProjectRule
from axm_audit.core.rules.test_quality._shared import (
    _FIXTURE_MOCK_PREFIXES,
    _FIXTURE_MOCK_SUBSTRS,
    _FIXTURE_NAME_SUFFIXES,
    _IO_FIXTURES,
    _IO_WRITER_ATTRS,
    analyze_imports,
    current_level_from_path,
    detect_real_io,
    func_attr_io_transitive,
    get_init_all,
    get_pkg_prefixes,
    iter_test_files,
)
from axm_audit.models.results import CheckResult, Severity

__all__ = [
    "Finding",
    "PyramidCheckResult",
    "PyramidLevelRule",
    "_classify_level",
    "_detect_tmp_path_usage",
    "_suggest_file",
    "scan_package",
    "scan_test_file",
]


_TMP_PATH_NAMES: frozenset[str] = frozenset({"tmp_path", "tmp_path_factory"})
_TAINT_PASSES = 2


class Finding(BaseModel):
    """One classification verdict for a single test function."""

    path: str
    function: str
    level: str
    reason: str
    current_level: str
    has_real_io: bool
    has_subprocess: bool
    io_signals: list[str] = Field(default_factory=list)
    imports_public: list[str] = Field(default_factory=list)
    imports_internal: list[str] = Field(default_factory=list)
    suggested_file: str = ""
    severity: Severity = Severity.WARNING

    model_config = {"extra": "forbid"}


class PyramidCheckResult(CheckResult):
    """:class:`CheckResult` subclass exposing ``findings`` and ``score``."""

    findings: list[Finding] = Field(default_factory=list)
    score: int = 100

    model_config = {"extra": "forbid"}


# ── Classification ────────────────────────────────────────────────────


def _classify_level(
    *,
    has_real_io: bool,
    has_subprocess: bool,
    imports_public: bool,
    imports_internal: bool,
) -> tuple[str, str]:
    """Return ``(level, reason)`` for the given soft signals.

    R2 public-only rescue MUST fire before the generic
    ``has_public \u2192 integration`` branch; otherwise pure-function unit
    tests at integration/ would be mis-classified.
    """
    if has_subprocess:
        return "e2e", "subprocess / CLI runner invocation (end-to-end)"
    if not has_real_io and imports_public and not imports_internal:
        return "unit", "public API import, no real I/O (pure function unit test)"
    if has_real_io:
        if imports_public:
            detail = " + public import"
        elif imports_internal:
            detail = " + internal import"
        else:
            detail = " without package import"
        return "integration", f"real I/O{detail} (integration)"
    if imports_internal:
        return "unit", "internal import, no real I/O (unit)"
    return "unit", "no real I/O, no package import (unit)"


# ── Per-function helpers ──────────────────────────────────────────────


def _func_references_names(func: ast.FunctionDef, names: set[str]) -> set[str]:
    """Return the subset of *names* that appear in *func* body."""
    hits: set[str] = set()
    if not names:
        return hits
    for node in ast.walk(func):
        if isinstance(node, ast.Name) and node.id in names:
            hits.add(node.id)
        elif isinstance(node, ast.Attribute):
            cur: ast.AST = node
            while isinstance(cur, ast.Attribute):
                cur = cur.value
            if isinstance(cur, ast.Name) and cur.id in names:
                hits.add(cur.id)
    return hits


def _is_mock_arg(name: str) -> bool:
    lower = name.lower()
    if any(lower.startswith(p) for p in _FIXTURE_MOCK_PREFIXES):
        return True
    return any(s in lower for s in _FIXTURE_MOCK_SUBSTRS)


def _fixture_io_signals(func: ast.FunctionDef) -> list[str]:
    sigs: list[str] = []
    for arg in func.args.args:
        name = arg.arg
        if name == "self":
            continue
        if _is_mock_arg(name):
            continue
        if name in _IO_FIXTURES or name.endswith(_FIXTURE_NAME_SUFFIXES):
            sigs.append(f"fixture-arg:{name}")
    return sigs


def _collect_taint_aliases(func: ast.FunctionDef) -> set[str]:
    """Two-pass propagation of ``tmp_path`` aliases through assignments."""
    tainted: set[str] = {
        arg.arg for arg in func.args.args if arg.arg in _TMP_PATH_NAMES
    }
    if not tainted:
        return tainted
    for _ in range(_TAINT_PASSES):
        changed = False
        for node in ast.walk(func):
            if not isinstance(node, ast.Assign):
                continue
            if not _expr_touches(node.value, tainted):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id not in tainted:
                    tainted.add(target.id)
                    changed = True
        if not changed:
            break
    return tainted


def _expr_touches(expr: ast.AST, names: set[str]) -> bool:
    for node in ast.walk(expr):
        if isinstance(node, ast.Name) and node.id in names:
            return True
    return False


def _tmp_path_reaches_call(func: ast.FunctionDef, tainted: set[str]) -> bool:
    if not tainted:
        return False
    for node in ast.walk(func):
        if not isinstance(node, ast.Call):
            continue
        for arg in node.args:
            if _expr_touches(arg, tainted):
                return True
        for kw in node.keywords:
            if kw.value is not None and _expr_touches(kw.value, tainted):
                return True
    return False


def _detect_tmp_path_usage(func: ast.FunctionDef) -> bool:
    """True if the function uses ``tmp_path`` **and** writes/reads through it."""
    uses_tmp = any(arg.arg in _TMP_PATH_NAMES for arg in func.args.args)
    if not uses_tmp:
        return False
    for node in ast.walk(func):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in _IO_WRITER_ATTRS or node.func.attr in (
                "read_text",
                "read_bytes",
            ):
                return True
    return False


# ── R4 / R5 stubs — replaced in ticket #4b ────────────────────────────


def _apply_conftest_fixture_io(_node: ast.FunctionDef) -> str | None:
    return None


def _apply_mock_neutralization(
    _node: ast.FunctionDef, signals: list[str]
) -> tuple[bool, list[str]]:
    return True, signals


# ── Suggested placement ───────────────────────────────────────────────


def _suggest_file(
    level: str,
    import_modules: list[str],
    pkg_prefixes: set[str],
    test_file: Path,
) -> str:
    """Return ``<level>/<sub>/test_<mod>.py`` if a pkg import is present."""
    chosen: str | None = None
    for mod in import_modules:
        parts = mod.split(".")
        if parts and parts[0] in pkg_prefixes:
            sub = parts[1:]
            if sub:
                chosen = "/".join([*sub[:-1], f"test_{sub[-1]}.py"])
                break
    if chosen is None:
        return f"{level}/{test_file.name}"
    return f"{level}/{chosen}"


# ── Scanning ──────────────────────────────────────────────────────────


def _collect_helpers(tree: ast.Module) -> dict[str, ast.FunctionDef]:
    helpers: dict[str, ast.FunctionDef] = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and not node.name.startswith("test_"):
            helpers[node.name] = node
    return helpers


def scan_test_file(  # noqa: PLR0912, PLR0913
    test_file: Path,
    tree: ast.Module,
    pkg_root: Path,
    pkg_prefixes: set[str],
    init_all: set[str] | None,
    tests_dir: Path,
) -> list[Finding]:
    """Classify every ``test_*`` function in *tree* and return findings.

    Emits one :class:`Finding` per function whose classified level differs
    from its folder-derived current level.
    """
    (
        public,
        internal,
        import_modules,
        _has_private,
        io_module_names,
        file_import_signals,
    ) = analyze_imports(tree, pkg_prefixes, init_all, pkg_root)

    file_has_io, file_has_subprocess, file_signals = detect_real_io(tree)
    helpers = _collect_helpers(tree)
    current = current_level_from_path(test_file, tests_dir)

    findings: list[Finding] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.FunctionDef) and node.name.startswith("test_")):
            continue

        has_real_io = False
        has_subprocess = file_has_subprocess
        signals: list[str] = []

        # R1 — module-level IO imports referenced in this function's body
        referenced = _func_references_names(node, io_module_names)
        for sig in file_import_signals:
            mod_from_sig = sig.removeprefix("imports ").split(".")[0]
            if any(
                ref == mod_from_sig or ref.startswith(mod_from_sig)
                for ref in referenced
            ):
                signals.append(sig)
                has_real_io = True

        # File-scope CLI runner / call-based I/O bleeds to every function
        if file_has_io:
            for sig in file_signals:
                if sig not in signals:
                    signals.append(sig)
            has_real_io = has_real_io or file_has_io

        # R3 — per-function attr-IO (transitive)
        attr_sigs = func_attr_io_transitive(node, helpers, max_depth=2)
        if attr_sigs:
            for sig in attr_sigs:
                if sig not in signals:
                    signals.append(sig)
            has_real_io = True

        # R3 — fixture-arg IO guard
        fixture_sigs = _fixture_io_signals(node)
        if fixture_sigs:
            signals.extend(fixture_sigs)
            has_real_io = True

        # R3 — tmp_path taint reaching any call
        tainted = _collect_taint_aliases(node)
        if _tmp_path_reaches_call(node, tainted):
            if "tmp_path-as-arg" not in signals:
                signals.append("tmp_path-as-arg")
            has_real_io = True

        # tmp_path boundary (write/read through tmp_path)
        if _detect_tmp_path_usage(node):
            if "tmp_path+write/read" not in signals:
                signals.append("tmp_path+write/read")
            has_real_io = True

        # R4 / R5 stubs — no-ops until ticket #4b replaces them
        _apply_conftest_fixture_io(node)
        _keep, signals = _apply_mock_neutralization(node, signals)

        level, reason = _classify_level(
            has_real_io=has_real_io,
            has_subprocess=has_subprocess,
            imports_public=bool(public),
            imports_internal=bool(internal),
        )
        suggested = _suggest_file(level, import_modules, pkg_prefixes, test_file)

        findings.append(
            Finding(
                path=str(test_file),
                function=node.name,
                level=level,
                reason=reason,
                current_level=current,
                has_real_io=has_real_io,
                has_subprocess=has_subprocess,
                io_signals=signals,
                imports_public=list(public),
                imports_internal=list(internal),
                suggested_file=suggested,
                severity=Severity.WARNING,
            )
        )

    return findings


def scan_package(pkg_root: Path) -> list[Finding]:
    """Scan every test file under ``<pkg_root>/tests`` and return findings."""
    tests_dir = pkg_root / "tests"
    if not tests_dir.exists():
        return []
    pkg_prefixes = get_pkg_prefixes(pkg_root)
    init_all = get_init_all(pkg_root)
    findings: list[Finding] = []
    for test_file, tree in iter_test_files(pkg_root):
        if tree is None:
            continue
        findings.extend(
            scan_test_file(test_file, tree, pkg_root, pkg_prefixes, init_all, tests_dir)
        )
    return findings


# ── Rule ──────────────────────────────────────────────────────────────


_SCORE_PENALTY = 2


@register_rule("test_quality")
@dataclass
class PyramidLevelRule(ProjectRule):
    """Report tests whose classified pyramid level mismatches their folder."""

    strict_mismatches: bool = True

    @property
    def rule_id(self) -> str:
        return "TEST_QUALITY_PYRAMID_LEVEL"

    def check(self, project_path: Path) -> PyramidCheckResult:
        tests_dir = project_path / "tests"
        if not tests_dir.exists():
            return PyramidCheckResult(
                rule_id=self.rule_id,
                passed=True,
                message="no tests/ directory",
                severity=Severity.INFO,
                score=100,
            )

        all_findings = scan_package(project_path)
        mismatches = [
            f for f in all_findings if f.current_level not in ("root", f.level)
        ]
        count = len(mismatches) if self.strict_mismatches else 0
        score = max(0, 100 - count * _SCORE_PENALTY)
        passed = count == 0
        message = (
            "pyramid levels match folder layout"
            if passed
            else f"{count} test(s) mis-located vs. classified pyramid level"
        )
        return PyramidCheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=message,
            severity=Severity.WARNING,
            findings=all_findings,
            score=score,
        )
