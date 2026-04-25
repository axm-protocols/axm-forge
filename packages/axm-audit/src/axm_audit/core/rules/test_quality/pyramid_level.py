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
from axm_audit.core.rules.test_quality import _shared
from axm_audit.core.rules.test_quality._shared import (
    _FIXTURE_MOCK_PREFIXES,
    _FIXTURE_MOCK_SUBSTRS,
    _FIXTURE_NAME_SUFFIXES,
    _IO_FIXTURES,
    _IO_WRITER_ATTRS,
    analyze_imports,
    current_level_from_path,
    detect_real_io,
    extract_mock_targets,
    fixture_does_io,
    func_attr_io_transitive,
    get_init_all,
    get_pkg_prefixes,
    iter_test_files,
    target_matches_io,
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


def _one_taint_pass(func: ast.FunctionDef, tainted: set[str]) -> bool:
    """Run one propagation pass; mutate ``tainted`` in place; return changed."""
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
    return changed


def _collect_taint_aliases(func: ast.FunctionDef) -> set[str]:
    """Two-pass propagation of ``tmp_path`` aliases through assignments."""
    tainted: set[str] = {
        arg.arg for arg in func.args.args if arg.arg in _TMP_PATH_NAMES
    }
    if not tainted:
        return tainted
    for _ in range(_TAINT_PASSES):
        if not _one_taint_pass(func, tainted):
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


# ── R4 — conftest fixture IO resolution ───────────────────────────────


def _gather_fixtures_for_test(
    tree: ast.Module,
    test_file: Path,
    tests_dir: Path,
    pkg_root: Path,
) -> dict[str, ast.FunctionDef]:
    """Collect fixtures from *tree* + every ``conftest.py`` ancestor to ``tests/``.

    Walk stops at ``tests_dir``, ``pkg_root`` or filesystem root, whichever
    comes first. Uses ``_shared._CONFTEST_CACHE`` to avoid re-parsing.
    """
    fixtures: dict[str, ast.FunctionDef] = dict(_shared._collect_fixtures(tree))
    current = test_file.parent.resolve()
    tests_dir = tests_dir.resolve()
    pkg_root = pkg_root.resolve()
    visited: set[Path] = set()
    while current not in visited:
        visited.add(current)
        conftest = current / "conftest.py"
        if conftest.exists():
            for name, fdef in _shared._load_conftest_fixtures(conftest).items():
                fixtures.setdefault(name, fdef)
        if current in (tests_dir, pkg_root):
            break
        parent = current.parent
        if parent == current:
            break
        current = parent
    return fixtures


def _apply_conftest_fixture_io(
    func: ast.FunctionDef,
    fixtures: dict[str, ast.FunctionDef],
) -> list[str]:
    """Emit ``conftest-fixture-io:<name>`` for each IO fixture the test takes."""
    signals: list[str] = []
    for arg in func.args.args:
        name = arg.arg
        if name == "self" or _is_mock_arg(name):
            continue
        if name not in fixtures:
            continue
        if fixture_does_io(name, fixtures, set(), 0):
            signals.append(f"conftest-fixture-io:{name}")
    return signals


# ── R5 — mock neutralization ──────────────────────────────────────────


def _signal_is_hard(sig: str) -> bool:
    if sig == "tmp_path+write/read":
        return True
    if sig.startswith("attr:."):
        attr = sig[len("attr:.") :].rstrip("()")
        return attr in _IO_WRITER_ATTRS
    return False


def _apply_mock_neutralization(
    func: ast.FunctionDef, signals: list[str]
) -> tuple[bool, list[str]]:
    """Neutralize soft-only signals when a mock covers an IO target.

    Returns ``(keep_has_real_io, signals)``. ``keep_has_real_io=False``
    means the caller must flip ``has_real_io`` to ``False``.
    """
    if any(_signal_is_hard(s) for s in signals):
        return True, signals
    targets = extract_mock_targets(func)
    if not targets:
        return True, signals
    has_io_target = any(
        not t.startswith("mock-factory:") and target_matches_io(t) for t in targets
    )
    has_factory = any(t.startswith("mock-factory:") for t in targets)
    if not (has_io_target or has_factory):
        return True, signals
    first_two = ",".join(targets[:2])
    return False, [*signals, f"mock-neutralized:{first_two}"]


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


def _collect_tmp_path_signals(
    node: ast.FunctionDef, signals: list[str]
) -> tuple[list[str], bool]:
    """Append tmp_path R3 markers (taint-as-arg, write/read) if applicable."""
    fired = False
    tainted = _collect_taint_aliases(node)
    if _tmp_path_reaches_call(node, tainted):
        if "tmp_path-as-arg" not in signals:
            signals.append("tmp_path-as-arg")
        fired = True
    if _detect_tmp_path_usage(node):
        if "tmp_path+write/read" not in signals:
            signals.append("tmp_path+write/read")
        fired = True
    return signals, fired


def _apply_r1_import_signals(
    node: ast.FunctionDef,
    io_module_names: set[str],
    file_import_signals: list[str],
    signals: list[str],
) -> bool:
    """Append R1 import-IO signals referenced by *node*; return whether any fired."""
    referenced = _func_references_names(node, io_module_names)
    fired = False
    for sig in file_import_signals:
        mod_from_sig = sig.removeprefix("imports ").split(".")[0]
        if any(
            ref == mod_from_sig or ref.startswith(mod_from_sig) for ref in referenced
        ):
            signals.append(sig)
            fired = True
    return fired


def _merge_unique(target: list[str], items: list[str]) -> None:
    """Append items from *items* into *target* preserving order, skipping duplicates."""
    for sig in items:
        if sig not in target:
            target.append(sig)


def _collect_signals(  # noqa: PLR0913
    node: ast.FunctionDef,
    *,
    io_module_names: set[str],
    file_import_signals: list[str],
    file_has_io: bool,
    file_signals: list[str],
    helpers: dict[str, ast.FunctionDef],
) -> tuple[list[str], bool, list[str]]:
    """Collect R1 + file-scope + R3 signals for *node*.

    Returns ``(signals, has_real_io, attr_sigs)``. ``attr_sigs`` is exposed
    so the caller can gate R4 (skipped when R3 attr-scan already fired).
    """
    signals: list[str] = []
    has_real_io = _apply_r1_import_signals(
        node, io_module_names, file_import_signals, signals
    )

    # File-scope CLI runner / call-based I/O bleeds to every function
    if file_has_io:
        _merge_unique(signals, file_signals)
        has_real_io = True

    # R3 — per-function attr-IO (transitive)
    attr_sigs = func_attr_io_transitive(node, helpers, max_depth=2)
    if attr_sigs:
        _merge_unique(signals, list(attr_sigs))
        has_real_io = True

    # R3 — fixture-arg IO guard
    fixture_sigs = _fixture_io_signals(node)
    signals.extend(fixture_sigs)
    has_real_io = has_real_io or bool(fixture_sigs)

    # R3 — tmp_path taint + boundary write/read
    signals, tmp_fired = _collect_tmp_path_signals(node, signals)
    if tmp_fired:
        has_real_io = True

    return signals, has_real_io, list(attr_sigs)


def _apply_r4_conftest(  # noqa: PLR0913
    node: ast.FunctionDef,
    tree: ast.Module,
    test_file: Path,
    tests_dir: Path,
    pkg_root: Path,
    fixtures: dict[str, ast.FunctionDef] | None,
    signals: list[str],
) -> tuple[list[str], bool, dict[str, ast.FunctionDef]]:
    """Apply R4 conftest-fixture IO scan and merge resulting signals.

    Returns ``(signals, fired, fixtures)`` where *fired* is ``True`` when
    the conftest scan produced at least one signal, and *fixtures* is the
    (possibly newly-computed) fixture cache for reuse across iterations.
    """
    if fixtures is None:
        fixtures = _gather_fixtures_for_test(tree, test_file, tests_dir, pkg_root)
    conftest_sigs = _apply_conftest_fixture_io(node, fixtures)
    for sig in conftest_sigs:
        if sig not in signals:
            signals.append(sig)
    return signals, bool(conftest_sigs), fixtures


@dataclass(slots=True)
class _ScanContext:
    """File-scope state shared across every ``test_*`` classification.

    Built once per test file by :func:`_build_scan_context`, then passed
    to :func:`_classify_test_function` for each test inside the module.
    ``fixtures`` is lazily populated by R4 on first conftest scan and
    reused across subsequent iterations.
    """

    test_file: Path
    tree: ast.Module
    pkg_root: Path
    pkg_prefixes: set[str]
    tests_dir: Path
    current: str
    public: list[str]
    internal: list[str]
    import_modules: list[str]
    io_module_names: set[str]
    file_import_signals: list[str]
    file_has_io: bool
    file_has_subprocess: bool
    file_signals: list[str]
    helpers: dict[str, ast.FunctionDef]
    fixtures: dict[str, ast.FunctionDef] | None = None


def _build_scan_context(  # noqa: PLR0913
    test_file: Path,
    tree: ast.Module,
    pkg_root: Path,
    pkg_prefixes: set[str],
    init_all: set[str] | None,
    tests_dir: Path,
) -> _ScanContext:
    """Gather all file-scope state needed to classify tests in *tree*."""
    (
        public,
        internal,
        import_modules,
        _has_private,
        io_module_names,
        file_import_signals,
    ) = analyze_imports(tree, pkg_prefixes, init_all, pkg_root)
    file_has_io, file_has_subprocess, file_signals = detect_real_io(tree)
    return _ScanContext(
        test_file=test_file,
        tree=tree,
        pkg_root=pkg_root,
        pkg_prefixes=pkg_prefixes,
        tests_dir=tests_dir,
        current=current_level_from_path(test_file, tests_dir),
        public=public,
        internal=internal,
        import_modules=import_modules,
        io_module_names=io_module_names,
        file_import_signals=file_import_signals,
        file_has_io=file_has_io,
        file_has_subprocess=file_has_subprocess,
        file_signals=file_signals,
        helpers=_collect_helpers(tree),
    )


def _resolve_io_for_test(
    ctx: _ScanContext, node: ast.FunctionDef
) -> tuple[list[str], bool, bool]:
    """Run R1+R3+R4+R5 and return ``(signals, has_real_io, has_subprocess)``."""
    signals, has_real_io, attr_sigs = _collect_signals(
        node,
        io_module_names=ctx.io_module_names,
        file_import_signals=ctx.file_import_signals,
        file_has_io=ctx.file_has_io,
        file_signals=ctx.file_signals,
        helpers=ctx.helpers,
    )
    has_subprocess = ctx.file_has_subprocess

    # R4 — conftest fixture IO (skipped when R3 attr-scan already fired)
    if not attr_sigs:
        signals, fired, ctx.fixtures = _apply_r4_conftest(
            node,
            ctx.tree,
            ctx.test_file,
            ctx.tests_dir,
            ctx.pkg_root,
            ctx.fixtures,
            signals,
        )
        has_real_io = has_real_io or fired

    # R5 — mock neutralization (hard invariant B: never fires on subprocess)
    if not has_subprocess:
        keep, signals = _apply_mock_neutralization(node, signals)
        if not keep:
            has_real_io = False

    return signals, has_real_io, has_subprocess


def _classify_test_function(ctx: _ScanContext, node: ast.FunctionDef) -> Finding:
    """Run the full pipeline for one ``test_*`` function and emit a Finding."""
    signals, has_real_io, has_subprocess = _resolve_io_for_test(ctx, node)
    level, reason = _classify_level(
        has_real_io=has_real_io,
        has_subprocess=has_subprocess,
        imports_public=bool(ctx.public),
        imports_internal=bool(ctx.internal),
    )
    suggested = _suggest_file(
        level, ctx.import_modules, ctx.pkg_prefixes, ctx.test_file
    )
    return Finding(
        path=str(ctx.test_file),
        function=node.name,
        level=level,
        reason=reason,
        current_level=ctx.current,
        has_real_io=has_real_io,
        has_subprocess=has_subprocess,
        io_signals=signals,
        imports_public=list(ctx.public),
        imports_internal=list(ctx.internal),
        suggested_file=suggested,
        severity=Severity.WARNING,
    )


def scan_test_file(  # noqa: PLR0913
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
    ctx = _build_scan_context(
        test_file, tree, pkg_root, pkg_prefixes, init_all, tests_dir
    )
    return [
        _classify_test_function(ctx, node)
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    ]


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
        """Stable identifier for this rule."""
        return "TEST_QUALITY_PYRAMID_LEVEL"

    def check(self, project_path: Path) -> PyramidCheckResult:
        """Classify tests in ``project_path`` against their pyramid folder."""
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
