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
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, Field

from axm_audit.core.rules.base import ProjectRule, register_rule
from axm_audit.core.rules.test_quality import _shared
from axm_audit.core.rules.test_quality._shared import (
    _FIXTURE_MOCK_PREFIXES,
    _FIXTURE_MOCK_SUBSTRS,
    _FIXTURE_NAME_SUFFIXES,
    _IO_ATTRS,
    _IO_CALLS,
    _IO_FIXTURES,
    _IO_WRITER_ATTRS,
    _dotted_call_name,
    analyze_imports,
    current_level_from_path,
    detect_real_io,
    extract_mock_targets,
    fixture_does_io,
    func_attr_io_transitive,
    get_init_all,
    get_pkg_prefixes,
    has_in_package_subprocess_invocation,
    iter_test_files,
    load_project_scripts,
    target_matches_io,
)
from axm_audit.models.results import CheckResult, Severity

__all__ = [
    "Finding",
    "PyramidCheckResult",
    "PyramidLevelRule",
    "_detect_tmp_path_usage",
    "_suggest_file",
    "has_in_package_subprocess_invocation",
    "load_project_scripts",
    "scan_package",
    "scan_test_file",
]


_TMP_PATH_NAMES: frozenset[str] = frozenset({"tmp_path", "tmp_path_factory"})

# Context-manager calls that catch the runtime effect of the wrapped block.
# When every reference to ``tmp_path`` lives inside one of these blocks the
# test exercises pre-flight validation, not real I/O.
_RAISES_CMS: frozenset[str] = frozenset({"raises", "warns", "deprecated_call"})

# Pure structural wrappers around a path-like value. ``str(tmp_path)`` /
# ``Path(tmp_path)`` / ``os.fspath(tmp_path)`` produce data, never I/O.
_STRUCTURAL_WRAPPERS: frozenset[str] = frozenset(
    {"str", "repr", "Path", "PurePath", "PurePosixPath", "PureWindowsPath", "fspath"}
)
_TAINT_PASSES = 2


class Finding(BaseModel):  # type: ignore[explicit-any]  # pydantic synthesizes __init__(**data: Any)
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


class PyramidCheckResult(CheckResult):  # type: ignore[explicit-any]  # pydantic synthesizes __init__(**data: Any)
    """:class:`CheckResult` subclass exposing ``findings`` and ``score``."""

    findings: list[Finding] = Field(default_factory=list)
    score: int = 100

    model_config = {"extra": "forbid"}


# ── Classification ────────────────────────────────────────────────────


def classify_level(
    *,
    has_real_io: bool,
    has_subprocess: bool,
    has_in_package_subprocess: bool,
    imports_public: bool,
    imports_internal: bool,
) -> tuple[str, str]:
    """Return ``(level, reason)`` for the given soft signals.

    ``has_subprocess`` preserves raw subprocess diagnostics, while
    ``has_in_package_subprocess`` is the narrower signal that promotes a test
    to e2e. R2 public-only rescue MUST fire before the generic
    ``has_public \u2192 integration`` branch; otherwise pure-function unit tests at
    integration/ would be mis-classified.
    """
    if has_in_package_subprocess:
        return "e2e", "in-package CLI invocation via subprocess (end-to-end)"
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


# `load_project_scripts` and `has_in_package_subprocess_invocation` are
# re-exported from ``_shared`` to preserve the public surface; the
# definitions live there (AC1, AXM-1721).


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


def _is_pytest_raises_call(call: ast.Call) -> bool:
    """True for ``pytest.raises(...)`` / ``raises(...)`` / ``pytest.warns(...)`` etc."""
    if isinstance(call.func, ast.Attribute):
        return call.func.attr in _RAISES_CMS
    if isinstance(call.func, ast.Name):
        return call.func.id in _RAISES_CMS
    return False


def _collect_pytest_raises_blocks(func: ast.FunctionDef) -> list[ast.With]:
    """Return every ``with pytest.raises(...)`` / ``pytest.warns(...)`` block."""
    blocks: list[ast.With] = []
    for node in ast.walk(func):
        if not isinstance(node, ast.With):
            continue
        if any(
            isinstance(item.context_expr, ast.Call)
            and _is_pytest_raises_call(item.context_expr)
            for item in node.items
        ):
            blocks.append(node)
    return blocks


def _node_inside_blocks(node: ast.AST, blocks: list[ast.With]) -> bool:
    """True if *node* is a descendant of any of the given ``with`` blocks."""
    if not blocks:
        return False
    return any(any(child is node for child in ast.walk(block)) for block in blocks)


def _is_class_constructor_call(call: ast.Call) -> bool:
    """True if *call* targets a PEP-8 capitalised name (class instantiation)."""
    target = call.func
    if isinstance(target, ast.Attribute):
        name = target.attr
    elif isinstance(target, ast.Name):
        name = target.id
    else:
        return False
    return bool(name) and name[0].isupper()


def _enclosing_call_for_name(
    name_node: ast.Name, func: ast.FunctionDef
) -> ast.Call | None:
    """Return the nearest enclosing ``ast.Call`` for *name_node*."""
    for node in ast.walk(func):
        if not isinstance(node, ast.Call):
            continue
        for sub in _call_subexprs(node):
            if any(child is name_node for child in ast.walk(sub)):
                return node
    return None


def _ctor_result_names(func: ast.FunctionDef, ctor_calls: set[int]) -> set[str]:
    """Names bound (``x = SomeClass(...)``) to one of the given ctor calls."""
    names: set[str] = set()
    for node in ast.walk(func):
        if not isinstance(node, ast.Assign):
            continue
        if not isinstance(node.value, ast.Call) or id(node.value) not in ctor_calls:
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                names.add(target.id)
    return names


def _method_call_touches_names(call: ast.Call, names: set[str]) -> bool:
    """True if a method call's receiver or any subexpr is a name in *names*."""
    if not isinstance(call.func, ast.Attribute):
        return False
    receiver = call.func.value
    if isinstance(receiver, ast.Name) and receiver.id in names:
        return True
    for sub in _call_subexprs(call):
        for child in ast.walk(sub):
            if isinstance(child, ast.Name) and child.id in names:
                return True
    return False


def _name_used_in_method_call(func: ast.FunctionDef, names: set[str]) -> bool:
    """True if any of *names* appears in a method call (receiver or arg)."""
    if not names:
        return False
    return any(
        isinstance(node, ast.Call) and _method_call_touches_names(node, names)
        for node in ast.walk(func)
    )


def _is_structural_wrapper_call(call: ast.Call) -> bool:
    """True for ``str(...)`` / ``Path(...)`` / ``os.fspath(...)`` etc."""
    target = call.func
    if isinstance(target, ast.Name):
        return target.id in _STRUCTURAL_WRAPPERS
    if isinstance(target, ast.Attribute):
        return target.attr in _STRUCTURAL_WRAPPERS
    return False


def _tmp_path_in_structural_wrapper(name_node: ast.Name, func: ast.FunctionDef) -> bool:
    """True if *name_node* sits inside a ``str()/Path()``-style wrapper call."""
    for node in ast.walk(func):
        if not isinstance(node, ast.Call) or not _is_structural_wrapper_call(node):
            continue
        for sub in _call_subexprs(node):
            if any(child is name_node for child in ast.walk(sub)):
                return True
    return False


def _classify_tmp_path_ref(
    node: ast.Name,
    func: ast.FunctionDef,
    raises_blocks: list[ast.With],
) -> tuple[bool, ast.Call | None]:
    """Decide whether *node* is a structural ``tmp_path`` reference.

    Returns ``(structural, ctor_call)`` where *ctor_call* is the
    capitalised-name call that consumes *node* when applicable (used by
    the caller to track bound names that must not later flow into method
    calls). ``structural=False`` means the reference escapes the
    heuristic and the whole function must be considered non-structural.
    """
    in_raises = _node_inside_blocks(node, raises_blocks)
    if in_raises and _tmp_path_in_structural_wrapper(node, func):
        return True, None
    enclosing = _enclosing_call_for_name(node, func)
    if enclosing is None:
        return False, None
    if _is_class_constructor_call(enclosing):
        return True, enclosing
    if in_raises and _is_structural_wrapper_call(enclosing):
        return True, None
    return False, None


def _tmp_path_uses_are_structural(func: ast.FunctionDef) -> bool:
    """True when every ``tmp_path`` reference is structural-only.

    A reference is structural when consumed by a capitalised-name call
    (PEP-8 class constructor — Pydantic/dataclass style) whose bound
    name is never re-used as a method-call receiver/argument, or when
    wrapped in a structural builtin (``str``, ``Path``, …) inside a
    ``with pytest.raises(...)`` / ``pytest.warns(...)`` block. The
    pytest.raises ancestor alone is NOT sufficient: a bare
    ``patch_makefile(tmp_path)`` inside ``pytest.raises`` still performs
    real I/O before the exception.
    """
    raises_blocks = _collect_pytest_raises_blocks(func)
    found_any = False
    ctor_calls: set[int] = set()
    for node in ast.walk(func):
        if not (isinstance(node, ast.Name) and node.id in _TMP_PATH_NAMES):
            continue
        found_any = True
        structural, ctor = _classify_tmp_path_ref(node, func, raises_blocks)
        if not structural:
            return False
        if ctor is not None:
            ctor_calls.add(id(ctor))
    if not found_any:
        return False
    bound_names = _ctor_result_names(func, ctor_calls)
    return not _name_used_in_method_call(func, bound_names)


def _fixture_io_signals(func: ast.FunctionDef) -> list[str]:
    sigs: list[str] = []
    structural_tmp = _tmp_path_uses_are_structural(func)
    for arg in func.args.args:
        name = arg.arg
        if name == "self":
            continue
        if _is_mock_arg(name):
            continue
        # ``tmp_path`` matches the generic ``_path`` suffix; suppress the
        # noisy ``fixture-arg:tmp_path`` signal when every reference is
        # structural (inside ``pytest.raises`` or only feeding a class
        # constructor). The dedicated ``_collect_tmp_path_signals`` scan
        # still catches real attr-IO and known-sink uses.
        if name in _TMP_PATH_NAMES and structural_tmp:
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


def _call_subexprs(call: ast.Call) -> Iterator[ast.expr]:
    yield from call.args
    yield from (kw.value for kw in call.keywords if kw.value is not None)


def _is_io_sink_call(call: ast.Call) -> bool:
    """True if *call* targets a known I/O sink.

    Recognises two shapes:

    * method call whose attribute is in :data:`_IO_ATTRS`
      (``p.write_text(...)``, ``p.mkdir(...)`` …);
    * dotted call whose fully-qualified name is in :data:`_IO_CALLS`
      (``subprocess.run(...)``, ``shutil.copy(...)`` …).

    Plain user-defined calls (``f(p)``, ``CopierConfig(destination=p)``,
    ``scaffold(str(p), ...)``) and structural builtins (``str``, ``Path``)
    return ``False`` — they do not perform I/O on their own.
    """
    if not isinstance(call.func, ast.Attribute):
        return False
    if call.func.attr in _IO_ATTRS:
        return True
    dotted = _dotted_call_name(call.func)
    return dotted is not None and dotted in _IO_CALLS


def _tmp_path_reaches_call(func: ast.FunctionDef, tainted: set[str]) -> bool:
    """True if tainted ``tmp_path`` aliases reach a known I/O sink call.

    Restricted to sinks recognised by :func:`_is_io_sink_call` so that
    passing ``tmp_path`` to a Pydantic constructor, ``pytest.raises``
    body, ``str()``/``Path()`` wrapper or any other plain user-defined
    function does NOT trip the ``tmp_path-as-arg`` signal.
    """
    if not tainted:
        return False
    for node in ast.walk(func):
        if not isinstance(node, ast.Call):
            continue
        if not _is_io_sink_call(node):
            continue
        if any(_expr_touches(expr, tainted) for expr in _call_subexprs(node)):
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
            for name, fdef in _shared.load_conftest_fixtures(conftest).items():
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
    if sig.startswith("conftest-fixture-io:"):
        return True
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
    # Also collect non-test methods defined inside test classes so that
    # `self._helper(...)` calls resolve through the same transitive I/O scan.
    # Module-level helpers win on name collision (setdefault).
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        for sub in node.body:
            if isinstance(sub, ast.FunctionDef) and not sub.name.startswith("test_"):
                helpers.setdefault(sub.name, sub)
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
    matched: list[str] = []
    for sig in file_import_signals:
        mod_from_sig = sig.removeprefix("imports ").split(".")[0]
        if any(
            ref == mod_from_sig or ref.startswith(mod_from_sig) for ref in referenced
        ):
            signals.append(sig)
            matched.append(sig)
    return _has_non_subprocess_io_signal(matched)


def _merge_unique(target: list[str], items: list[str]) -> None:
    """Append items from *items* into *target* preserving order, skipping duplicates."""
    for sig in items:
        if sig not in target:
            target.append(sig)


def _is_subprocess_only_signal(sig: str) -> bool:
    return (
        sig == "imports subprocess"
        or sig.startswith("imports subprocess.")
        or sig.startswith("call:subprocess.")
        or sig.startswith("cli:")
    )


def _has_non_subprocess_io_signal(signals: list[str]) -> bool:
    return any(not _is_subprocess_only_signal(sig) for sig in signals)


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
        has_real_io = has_real_io or _has_non_subprocess_io_signal(file_signals)

    # R3 — per-function attr-IO (transitive)
    attr_sigs = func_attr_io_transitive(node, helpers, max_depth=2)
    if attr_sigs:
        _merge_unique(signals, list(attr_sigs))
        has_real_io = has_real_io or _has_non_subprocess_io_signal(list(attr_sigs))

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
    project_scripts: set[str]
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
        project_scripts=load_project_scripts(pkg_root),
        helpers=_collect_helpers(tree),
    )


def _resolve_io_for_test(
    ctx: _ScanContext, node: ast.FunctionDef
) -> tuple[list[str], bool, bool, bool]:
    """Return signals plus real I/O, raw subprocess, and in-package subprocess."""
    signals, has_real_io, attr_sigs = _collect_signals(
        node,
        io_module_names=ctx.io_module_names,
        file_import_signals=ctx.file_import_signals,
        file_has_io=ctx.file_has_io,
        file_signals=ctx.file_signals,
        helpers=ctx.helpers,
    )
    has_subprocess = ctx.file_has_subprocess
    has_in_package_subprocess = _has_in_package_subprocess_for_test(ctx, node)

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

    # R5 — mock neutralization (hard invariant B: never fires on in-package subprocess)
    if not has_in_package_subprocess:
        keep, signals = _apply_mock_neutralization(node, signals)
        if not keep:
            has_real_io = False

    return signals, has_real_io, has_subprocess, has_in_package_subprocess


def _helper_callees(node: ast.AST, helpers: dict[str, ast.FunctionDef]) -> list[str]:
    """Names directly called inside ``node`` that resolve in ``helpers``."""
    out: list[str] = []
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Call):
            continue
        func = sub.func
        name = (
            func.id
            if isinstance(func, ast.Name)
            else func.attr
            if isinstance(func, ast.Attribute)
            else None
        )
        if name is not None and name in helpers:
            out.append(name)
    return out


def _closure_bodies(
    test_node: ast.FunctionDef, helpers: dict[str, ast.FunctionDef]
) -> list[ast.AST]:
    """Return test body + transitively-called module-level helper bodies.

    Follows ``ast.Name`` and ``ast.Attribute`` callees that resolve in
    ``helpers``. Scope is intentionally narrow: only module-level helpers
    (and non-test methods of Test* classes already merged into ``helpers``).
    """
    seen: set[str] = set()
    stack: list[str] = list(_helper_callees(test_node, helpers))
    while stack:
        name = stack.pop()
        if name in seen:
            continue
        seen.add(name)
        stack.extend(
            cand for cand in _helper_callees(helpers[name], helpers) if cand not in seen
        )
    return [test_node, *(helpers[n] for n in seen)]


def _has_in_package_subprocess_for_test(
    ctx: _ScanContext, node: ast.FunctionDef
) -> bool:
    if not ctx.file_has_subprocess:
        return False
    if any(sig.startswith("cli:") for sig in ctx.file_signals):
        return True
    if not ctx.project_scripts:
        return False
    bodies = _closure_bodies(node, ctx.helpers)
    return any(
        has_in_package_subprocess_invocation(
            call=call,
            module_ast=ctx.tree,
            project_scripts=ctx.project_scripts,
        )
        for body in bodies
        for call in ast.walk(body)
        if isinstance(call, ast.Call)
    )


def _classify_test_function(ctx: _ScanContext, node: ast.FunctionDef) -> Finding:
    """Run the full pipeline for one ``test_*`` function and emit a Finding."""
    (
        signals,
        has_real_io,
        has_subprocess,
        has_in_package_subprocess,
    ) = _resolve_io_for_test(ctx, node)
    level, reason = classify_level(
        has_real_io=has_real_io,
        has_subprocess=has_subprocess,
        has_in_package_subprocess=has_in_package_subprocess,
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


def _filter_mismatches(findings: list[Finding], tests_dir: Path) -> list[Finding]:
    """Return findings whose location does not match their classified level.

    When the package has opted into the pyramid (any of ``unit``,
    ``integration``, ``e2e`` exists under ``tests_dir``), root-level tests
    count as mismatches. Otherwise the legacy lenient behavior is preserved.
    """
    pyramid_opted_in = any(
        (tests_dir / sub).is_dir() for sub in ("unit", "integration", "e2e")
    )
    if pyramid_opted_in:
        return [f for f in findings if f.current_level != f.level]
    return [f for f in findings if f.current_level not in ("root", f.level)]


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
_MAX_TEXT_ITEMS = 20


def relpath(path: str, project_path: Path) -> str:
    """Return *path* relative to *project_path* if possible, else absolute."""
    try:
        return str(Path(path).relative_to(project_path))
    except ValueError:
        return path


def render_mismatch_text(mismatches: list[Finding], project_path: Path) -> str:
    """Render top-N mismatched findings as a compact bullet list.

    Paths are relativized to *project_path* to keep the text dense; falls
    back to the absolute path if the finding lives outside the project root.
    """
    lines = [
        f"• {relpath(f.path, project_path)}:{f.function} "
        f"{f.current_level}→{f.level} ({f.reason})"
        for f in mismatches[:_MAX_TEXT_ITEMS]
    ]
    if len(mismatches) > _MAX_TEXT_ITEMS:
        lines.append(f"(+{len(mismatches) - _MAX_TEXT_ITEMS} more)")
    return "\n".join(lines)


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
        mismatches = _filter_mismatches(all_findings, tests_dir)
        count = len(mismatches) if self.strict_mismatches else 0
        score = max(0, 100 - count * _SCORE_PENALTY)
        passed = count == 0
        message = (
            "pyramid levels match folder layout"
            if passed
            else f"{count} test(s) mis-located vs. classified pyramid level"
        )
        details: dict[str, object] = {
            "mismatches": [f.model_dump() for f in mismatches],
            "total": len(mismatches),
        }
        text = render_mismatch_text(mismatches, project_path) if mismatches else None
        fix_hint = (
            None
            if passed
            else "Move tests to matching pyramid dir (use /pyramid-relocate)"
        )
        return PyramidCheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=message,
            severity=Severity.WARNING,
            findings=all_findings,
            score=score,
            details=details,
            text=text,
            fix_hint=fix_hint,
        )
