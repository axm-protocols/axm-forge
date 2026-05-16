"""Shared AST primitives for ``test_quality`` rules.

Registry-neutral helpers ported from the ``detect_pyramid_level_v6`` and
``triage_tautologies_v4`` prototypes.  Rules in this subpackage import
from here; no ``@register_rule`` lives here.
"""

from __future__ import annotations

import ast
import tomllib
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from axm_audit.core.rules._helpers import get_ast_cache, parse_file_safe

__all__ = [
    "analyze_imports",
    "canonical_filename",
    "cli_invocation_tuple",
    "collect_pkg_contract_classes",
    "collect_pkg_public_symbols",
    "current_level_from_path",
    "detect_real_io",
    "extract_mock_targets",
    "first_party_symbol_counts",
    "fixture_does_io",
    "func_attr_io_transitive",
    "get_init_all",
    "get_module_all",
    "get_pkg_prefixes",
    "has_in_package_subprocess_invocation",
    "is_import_smoke_test",
    "iter_test_files",
    "load_project_scripts",
    "target_matches_io",
    "test_invokes_in_package_script",
    "test_is_in_lazy_import_context",
    "test_references_first_party",
    "to_snake_token",
]


_IO_FIXTURES: frozenset[str] = frozenset(
    {
        "tmp_path_factory",
        "httpx_mock",
        "respx_mock",
        "mock_server",
        "test_db",
        "live_server",
        "aiohttp_client",
        "aioresponses",
        "requests_mock",
        "database",
        "session",
        "async_session",
        "redis_client",
        "ftp_server",
        "smtp_server",
    }
)

_FIXTURE_NAME_SUFFIXES: tuple[str, ...] = (
    "_db",
    "_client",
    "_server",
    "_session",
    "_engine",
    "_workspace",
    "_pkg",
    "_project",
    "_repo",
    "_path",
    "_dir",
    "_file",
)

_FIXTURE_MOCK_PREFIXES: tuple[str, ...] = ("mock_", "stub_")
_FIXTURE_MOCK_SUBSTRS: tuple[str, ...] = ("mock", "stub")

_IO_CALLS: frozenset[str] = frozenset(
    {
        "subprocess.run",
        "subprocess.call",
        "subprocess.check_output",
        "subprocess.check_call",
        "subprocess.Popen",
        "os.system",
        "os.popen",
        "socket.socket",
        "socket.create_connection",
        "urllib.request.urlopen",
        "urllib.urlopen",
        "requests.get",
        "requests.post",
        "requests.put",
        "requests.delete",
        "requests.request",
        "requests.head",
        "requests.patch",
        "httpx.get",
        "httpx.post",
        "httpx.put",
        "httpx.delete",
        "httpx.request",
        "httpx.Client",
        "httpx.AsyncClient",
        "sqlite3.connect",
        "psycopg2.connect",
        "asyncpg.connect",
        "redis.Redis",
        "redis.StrictRedis",
        "shutil.copyfile",
        "shutil.copy",
        "shutil.copy2",
        "shutil.copytree",
        "shutil.move",
        "shutil.rmtree",
    }
)

_IO_ATTRS: frozenset[str] = frozenset(
    {
        "write_text",
        "write_bytes",
        "read_text",
        "read_bytes",
        "mkdir",
        "rmdir",
        "unlink",
        "rename",
        "replace",
        "makedirs",
        "removedirs",
        "touch",
        "symlink_to",
        "hardlink_to",
        "chmod",
        "chown",
        "iterdir",
        "glob",
        "rglob",
        "is_file",
        "is_dir",
        "exists",
        "stat",
        "lstat",
    }
)

_IO_WRITER_ATTRS: frozenset[str] = frozenset(
    {
        "write_text",
        "write_bytes",
        "mkdir",
        "rmdir",
        "unlink",
        "rename",
        "replace",
        "makedirs",
        "removedirs",
        "touch",
        "symlink_to",
        "hardlink_to",
        "chmod",
        "chown",
    }
)

_IO_MODULES: frozenset[str] = frozenset(
    {
        "subprocess",
        "socket",
        "urllib.request",
        "urllib",
        "requests",
        "httpx",
        "aiohttp",
        "sqlite3",
        "psycopg2",
        "asyncpg",
        "mysqlclient",
        "redis",
        "pymongo",
        "ftplib",
        "smtplib",
        "imaplib",
        "telnetlib",
        "shutil",
    }
)

_CLI_RUNNER_CLASSES: frozenset[str] = frozenset({"CliRunner", "CycloptsRunner"})
_CLI_RUNNER_NAMES: frozenset[str] = frozenset({"CliRunner", "runner", "invoke"})

_MOCK_FACTORIES: frozenset[str] = frozenset(
    {
        "Mock",
        "MagicMock",
        "AsyncMock",
        "NonCallableMock",
        "NonCallableMagicMock",
        "PropertyMock",
    }
)

_LAZY_FILENAMES: frozenset[str] = frozenset(
    {
        "test_init.py",
        "test_package.py",
        "test_imports.py",
        "test___init__.py",
    }
)

_LAZY_DOCSTRING_SIGNALS: tuple[str, ...] = (
    "__getattr__",
    "lazy",
    "re-export",
    "reexport",
    "entry_points",
    "entry-points",
    "importlib",
    "lazy-import",
    "lazy import",
)

_LAZY_CLASSNAME_SIGNALS: tuple[str, ...] = (
    "lazyimport",
    "reexport",
    "re-export",
    "exposure",
    "package",
)

_FIXTURE_DEPTH_LIMIT = 3
_SMOKE_BODY_BUDGET = 4
_SETATTR_OBJ_FORM_MIN_ARGS = 2

_CONFTEST_CACHE: dict[Path, dict[str, ast.FunctionDef]] = {}


# ── File / package enumeration ────────────────────────────────────────


def _parse_cached(path: Path) -> ast.Module | None:
    cache = get_ast_cache()
    if cache is not None:
        return cache.get_or_parse(path)
    return parse_file_safe(path)


def iter_test_files(pkg_root: Path) -> Iterator[tuple[Path, ast.Module | None]]:
    """Yield ``(path, ast)`` for every ``tests/**/test_*.py``."""
    tests_dir = pkg_root / "tests"
    if not tests_dir.exists():
        return
    for test_file in sorted(tests_dir.rglob("test_*.py")):
        yield test_file, _parse_cached(test_file)


def get_pkg_prefixes(pkg_root: Path) -> set[str]:
    """Return top-level package directory names under ``<pkg_root>/src``.

    Args:
        pkg_root: Repository root expected to follow the ``src/`` layout.

    Returns:
        Set of directory names directly under ``src``, excluding hidden
        entries. Empty when ``src`` is missing.
    """
    src_dir = pkg_root / "src"
    if not src_dir.exists():
        return set()
    return {
        d.name for d in src_dir.iterdir() if d.is_dir() and not d.name.startswith(".")
    }


def _is_all_target(node: ast.AST) -> bool:
    return isinstance(node, ast.Name) and node.id == "__all__"


def _extract_all_from_tree(tree: ast.Module) -> set[str] | None:
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            _is_all_target(t) for t in node.targets
        ):
            return _literal_strings(node.value)
        if isinstance(node, ast.AugAssign) and _is_all_target(node.target):
            return _literal_strings(node.value)
    return None


def _literal_strings(expr: ast.AST) -> set[str] | None:
    if not isinstance(expr, (ast.List, ast.Tuple, ast.Set)):
        return None
    out: set[str] = set()
    for elt in expr.elts:
        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
            out.add(elt.value)
    return out


def get_init_all(pkg_root: Path) -> set[str] | None:
    """Read ``__all__`` from the first ``src/<pkg>/__init__.py`` that defines it.

    Args:
        pkg_root: Repository root expected to follow the ``src/`` layout.

    Returns:
        Set of exported names, or ``None`` when no top-level package
        declares ``__all__`` (or ``src`` is missing).
    """
    src_dir = pkg_root / "src"
    if not src_dir.exists():
        return None
    for pkg_dir in src_dir.iterdir():
        if not pkg_dir.is_dir() or pkg_dir.name.startswith("."):
            continue
        init = pkg_dir / "__init__.py"
        if not init.exists():
            continue
        tree = _parse_cached(init)
        if tree is None:
            continue
        found = _extract_all_from_tree(tree)
        if found is not None:
            return found
    return None


def get_module_all(pkg_root: Path, dotted: str) -> set[str] | None:
    """Resolve ``__all__`` for ``dotted`` module within the ``src`` tree.

    Args:
        pkg_root: Repository root expected to follow the ``src/`` layout.
        dotted: Dotted module path relative to ``src`` (e.g. ``pkg.sub``).

    Returns:
        Set of exported names, or ``None`` if the module is missing or does
        not declare ``__all__``.
    """
    src_dir = pkg_root / "src"
    rel = dotted.replace(".", "/")
    candidates = [src_dir / (rel + ".py"), src_dir / rel / "__init__.py"]
    for cand in candidates:
        if not cand.exists():
            continue
        tree = _parse_cached(cand)
        if tree is None:
            continue
        found = _extract_all_from_tree(tree)
        if found is not None:
            return found
    return None


def current_level_from_path(test_file: Path, tests_dir: Path) -> str:
    """Map ``test_file`` to its pyramid level based on its location.

    Args:
        test_file: Test file path to classify.
        tests_dir: Root tests directory used to compute the relative path.

    Returns:
        One of ``"unit"``, ``"integration"``, ``"e2e"``, or ``"root"`` when
        the level cannot be inferred. ``functional`` folders are mapped to
        ``"integration"`` for backward compatibility.
    """
    try:
        rel = test_file.relative_to(tests_dir)
    except ValueError:
        return "root"
    parts = rel.parts
    if len(parts) > 1:
        first = parts[0]
        if first in ("unit", "integration", "e2e"):
            return first
        if first == "functional":
            return "integration"
    return "root"


# ── Import analysis ───────────────────────────────────────────────────


@dataclass
class _ImportScan:
    """Mutable accumulator for :func:`analyze_imports` classification."""

    public: list[str] = field(default_factory=list)
    internal: list[str] = field(default_factory=list)
    import_modules: list[str] = field(default_factory=list)
    io_module_names: set[str] = field(default_factory=set)
    io_signals: list[str] = field(default_factory=list)
    has_private: bool = False


def _is_io_module(mod: str) -> bool:
    return mod in _IO_MODULES or any(mod.startswith(m + ".") for m in _IO_MODULES)


def _is_pkg_module(mod: str, pkg_prefixes: set[str]) -> bool:
    return any(mod == p or mod.startswith(p + ".") for p in pkg_prefixes)


def _classify_alias_name(
    name: str,
    init_all: set[str] | None,
    mod_all: set[str] | None,
) -> str:
    """Return one of ``'private'``, ``'public'``, ``'internal'``."""
    if name.startswith("_") and not (name.startswith("__") and name.endswith("__")):
        return "private"
    in_root_all = init_all is not None and name in init_all
    in_mod_all = mod_all is not None and name in mod_all
    return "public" if (in_root_all or in_mod_all) else "internal"


def _classify_pkg_aliases(
    node: ast.ImportFrom,
    init_all: set[str] | None,
    mod_all: set[str] | None,
    scan: _ImportScan,
) -> None:
    for alias in node.names or []:
        kind = _classify_alias_name(alias.name, init_all, mod_all)
        if kind == "private":
            scan.has_private = True
            scan.internal.append(alias.name)
        elif kind == "public":
            scan.public.append(alias.name)
        else:
            scan.internal.append(alias.name)


def _process_import_from(
    node: ast.ImportFrom,
    pkg_prefixes: set[str],
    init_all: set[str] | None,
    pkg_root: Path,
    scan: _ImportScan,
) -> None:
    mod = node.module or ""
    if _is_io_module(mod):
        scan.io_signals.append(f"imports {mod}")
        for alias in node.names or []:
            scan.io_module_names.add(alias.asname or alias.name)
        return
    if not _is_pkg_module(mod, pkg_prefixes):
        return
    if mod not in scan.import_modules:
        scan.import_modules.append(mod)
    mod_all = get_module_all(pkg_root, mod)
    _classify_pkg_aliases(node, init_all, mod_all, scan)


def _process_import(node: ast.Import, scan: _ImportScan) -> None:
    for alias in node.names:
        if alias.name in _IO_MODULES:
            scan.io_signals.append(f"imports {alias.name}")
            scan.io_module_names.add(alias.asname or alias.name.split(".")[0])


def analyze_imports(
    tree: ast.Module,
    pkg_prefixes: set[str],
    init_all: set[str] | None,
    pkg_root: Path,
) -> tuple[list[str], list[str], list[str], bool, set[str], list[str]]:
    """Classify imports + collect IO module names.

    Returns ``(public, internal, modules, has_private, io_module_names,
    io_signals)``.
    """
    scan = _ImportScan()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            _process_import_from(node, pkg_prefixes, init_all, pkg_root, scan)
        elif isinstance(node, ast.Import):
            _process_import(node, scan)
    return (
        scan.public,
        scan.internal,
        scan.import_modules,
        scan.has_private,
        scan.io_module_names,
        scan.io_signals,
    )


# ── IO detection ──────────────────────────────────────────────────────


_STR_REPLACE_MIN_ARGS = 2


def _is_literal_str_replace(call: ast.Call) -> bool:
    """True for ``.replace("x", "y")`` with two string-literal args.

    ``str.replace`` and ``Path.replace`` share the same name but only the
    latter is I/O. Without type inference we use a syntactic guard: real
    file renames pass a path-like argument, never two string literals.
    """
    if not isinstance(call.func, ast.Attribute) or call.func.attr != "replace":
        return False
    if len(call.args) < _STR_REPLACE_MIN_ARGS:
        return False
    return all(
        isinstance(a, ast.Constant) and isinstance(a.value, str)
        for a in call.args[:_STR_REPLACE_MIN_ARGS]
    )


def _attr_signals_in_node(node: ast.AST) -> list[str]:
    sigs: list[str] = []
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        if isinstance(child.func, ast.Attribute) and child.func.attr in _IO_ATTRS:
            if _is_literal_str_replace(child):
                continue
            sigs.append(f"attr:.{child.func.attr}()")
        if isinstance(child.func, ast.Name) and child.func.id == "open":
            sigs.append("call:open()")
    return sigs


def _resolve_call_target(call: ast.Call) -> str | None:
    """Return the lookup name for ``call`` or ``None`` if unresolvable.

    Bare names resolve to themselves; ``self.<attr>(...)`` resolves to the
    method name so class helpers can be looked up; chained attribute calls
    resolve to the leftmost name (e.g. ``a.b.c()`` -> ``a``).
    """
    func = call.func
    if isinstance(func, ast.Name):
        return func.id
    if not isinstance(func, ast.Attribute):
        return None
    # `self.<attr>(...)` resolves to the method name, not `self`.
    if isinstance(func.value, ast.Name) and func.value.id == "self":
        return func.attr
    cur: ast.AST = func
    while isinstance(cur, ast.Attribute):
        cur = cur.value
    return cur.id if isinstance(cur, ast.Name) else None


def _names_called_in(node: ast.AST) -> set[str]:
    """Collect resolvable call-target names reachable from ``node``."""
    return {
        name
        for child in ast.walk(node)
        if isinstance(child, ast.Call)
        and (name := _resolve_call_target(child)) is not None
    }


def _fixture_arg_signals(tree: ast.Module) -> list[str]:
    signals: list[str] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.FunctionDef) and node.name.startswith("test_")):
            continue
        for arg in node.args.args:
            if arg.arg in _IO_FIXTURES:
                signals.append(f"fixture:{arg.arg}")
    return signals


def _dotted_call_name(func: ast.Attribute) -> str | None:
    """Return the dotted name of an attribute call target, or ``None``."""
    parts: list[str] = []
    cur: ast.AST = func
    while isinstance(cur, ast.Attribute):
        parts.insert(0, cur.attr)
        cur = cur.value
    if not isinstance(cur, ast.Name):
        return None
    parts.insert(0, cur.id)
    return ".".join(parts)


def _io_call_signals(tree: ast.Module) -> tuple[bool, list[str]]:
    has_subprocess = False
    signals: list[str] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        full = _dotted_call_name(node.func)
        if full is None or full not in _IO_CALLS:
            continue
        signals.append(f"call:{full}")
        if full.startswith("subprocess."):
            has_subprocess = True
    return has_subprocess, signals


def _cli_runner_signal(node: ast.Call) -> str | None:
    # ``runner.invoke(...)`` / ``CliRunner().invoke(...)``
    if isinstance(node.func, ast.Attribute) and node.func.attr == "invoke":
        target = node.func.value
        if isinstance(target, ast.Call) and isinstance(target.func, ast.Name):
            if target.func.id in _CLI_RUNNER_CLASSES:
                return f"cli:{target.func.id}"
        if isinstance(target, ast.Name) and target.id in _CLI_RUNNER_NAMES:
            return f"cli:{target.id}"
    # ``cli_runner(args)`` — fixture-style direct call (cyclopts convention)
    if isinstance(node.func, ast.Name) and node.func.id == "cli_runner":
        return "cli:cli_runner"
    return None


def _cli_runner_signals(tree: ast.Module) -> tuple[bool, list[str]]:
    signals: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        sig = _cli_runner_signal(node)
        if sig is not None:
            signals.append(sig)
    return bool(signals), signals


def detect_real_io(tree: ast.Module) -> tuple[bool, bool, list[str]]:
    """File-scope I/O detection from a parsed test module.

    Scans the module for three kinds of evidence that a test performs real I/O:
    fixtures listed in ``_IO_FIXTURES`` consumed by ``test_*`` functions,
    dotted calls listed in ``_IO_CALLS`` (e.g. ``subprocess.run``,
    ``pathlib.Path.write_text``), and CLI runner invocations such as
    ``CliRunner().invoke(...)``. Attribute-IO inside helpers is intentionally
    out of scope — see :func:`func_attr_io_transitive`.

    Returns:
        ``(has_io, has_subprocess, signals)``. ``has_io`` is ``True`` when any
        signal was found. ``has_subprocess`` is ``True`` when a
        ``subprocess.*`` call or a CLI runner was seen. ``signals`` is the
        list of evidence strings (``fixture:<name>``, ``call:<dotted>``,
        ``cli:<runner>``) preserving discovery order.
    """
    fixture_signals = _fixture_arg_signals(tree)
    sub_from_calls, call_signals = _io_call_signals(tree)
    sub_from_cli, cli_signals = _cli_runner_signals(tree)

    signals = fixture_signals + call_signals + cli_signals
    has_io = bool(signals)
    has_subprocess = sub_from_calls or sub_from_cli
    return has_io, has_subprocess, signals


def func_attr_io_transitive(
    func: ast.FunctionDef,
    helpers: dict[str, ast.FunctionDef],
    max_depth: int = 2,
) -> list[str]:
    """Attr-IO signals over the function subtree + transitively reachable helpers."""
    visited: set[str] = set()
    sigs: list[str] = list(_attr_signals_in_node(func))

    frontier = _names_called_in(func) & set(helpers.keys())
    depth = 1
    while frontier and depth <= max_depth:
        next_frontier: set[str] = set()
        for name in frontier:
            if name in visited:
                continue
            visited.add(name)
            sigs.extend(_attr_signals_in_node(helpers[name]))
            next_frontier |= _names_called_in(helpers[name]) & set(helpers.keys())
        frontier = next_frontier - visited
        depth += 1
    return sigs


# ── Fixture resolution ────────────────────────────────────────────────


def _is_pytest_fixture(func: ast.FunctionDef) -> bool:
    for deco in func.decorator_list:
        if isinstance(deco, ast.Attribute) and deco.attr == "fixture":
            return True
        if isinstance(deco, ast.Call) and isinstance(deco.func, ast.Attribute):
            if deco.func.attr == "fixture":
                return True
        if isinstance(deco, ast.Name) and deco.id == "fixture":
            return True
    return False


def _collect_fixtures(tree: ast.Module) -> dict[str, ast.FunctionDef]:
    out: dict[str, ast.FunctionDef] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and _is_pytest_fixture(node):
            out.setdefault(node.name, node)
    return out


def load_conftest_fixtures(conftest: Path) -> dict[str, ast.FunctionDef]:
    key = conftest.resolve()
    cached = _CONFTEST_CACHE.get(key)
    if cached is not None:
        return cached
    fixtures: dict[str, ast.FunctionDef] = {}
    try:
        source = conftest.read_text()
        tree = ast.parse(source, filename=str(conftest))
        fixtures = _collect_fixtures(tree)
    except (OSError, SyntaxError, UnicodeDecodeError):
        pass
    _CONFTEST_CACHE[key] = fixtures
    return fixtures


def _expr_contains_names(expr: ast.AST, names: set[str]) -> bool:
    for node in ast.walk(expr):
        if isinstance(node, ast.Name) and node.id in names:
            return True
    return False


def _fixture_has_direct_io(fdef: ast.FunctionDef) -> bool:
    """True if fixture body has direct attr-IO or matches ``_IO_CALLS``."""
    if _attr_signals_in_node(fdef):
        return True
    for node in ast.walk(fdef):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        parts: list[str] = []
        cur: ast.AST = node.func
        while isinstance(cur, ast.Attribute):
            parts.insert(0, cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name):
            parts.insert(0, cur.id)
            if ".".join(parts) in _IO_CALLS:
                return True
    return False


def _fixture_calls_io_fixture(
    fdef: ast.FunctionDef,
    fix_name: str,
    fixtures: dict[str, ast.FunctionDef],
    visited: set[str],
    depth: int,
) -> bool:
    """True if fixture transitively depends on ``tmp_path`` or another IO fixture."""
    for arg in fdef.args.args:
        if arg.arg in ("tmp_path", "tmp_path_factory") and _expr_contains_names(
            fdef, {arg.arg}
        ):
            return True
        if (
            arg.arg in fixtures
            and arg.arg != fix_name
            and fixture_does_io(arg.arg, fixtures, visited, depth + 1)
        ):
            return True
    return False


def fixture_does_io(
    fix_name: str,
    fixtures: dict[str, ast.FunctionDef],
    visited: set[str],
    depth: int,
) -> bool:
    """True if fixture body does real I/O.

    Walks the fixture body for attr-IO, ``_IO_CALLS`` matches and
    transitive ``tmp_path`` deps; depth-bounded by ``_FIXTURE_DEPTH_LIMIT``.
    """
    if fix_name in visited or depth >= _FIXTURE_DEPTH_LIMIT:
        return False
    visited.add(fix_name)
    fdef = fixtures.get(fix_name)
    if fdef is None:
        return False
    return _fixture_has_direct_io(fdef) or _fixture_calls_io_fixture(
        fdef, fix_name, fixtures, visited, depth
    )


# ── Package surface ───────────────────────────────────────────────────


def _iter_src_py(pkg_root: Path) -> Iterator[Path]:
    src = pkg_root / "src"
    if not src.exists():
        return
    yield from sorted(src.rglob("*.py"))


def _public_names_from_node(node: ast.stmt) -> Iterator[str]:
    match node:
        case (
            ast.FunctionDef(name=name)
            | ast.AsyncFunctionDef(name=name)
            | ast.ClassDef(name=name)
        ):
            if not name.startswith("_"):
                yield name
        case ast.Assign(targets=targets):
            for target in targets:
                if isinstance(target, ast.Name) and not target.id.startswith("_"):
                    yield target.id
        case ast.AnnAssign(target=ast.Name(id=tid)) if not tid.startswith("_"):
            yield tid


def collect_pkg_public_symbols(pkg_root: Path) -> set[str]:
    """Collect top-level public function, class, and constant names across ``src/``.

    Walks every ``*.py`` file under ``{pkg_root}/src`` and returns the union of
    non-underscore names defined at module top level — functions, async
    functions, classes, and simple / annotated assignments to ``Name`` targets.
    """
    out: set[str] = set()
    for path in _iter_src_py(pkg_root):
        tree = _parse_cached(path)
        if tree is None:
            continue
        for node in tree.body:
            out.update(_public_names_from_node(node))
    return out


_CONTRACT_BASES: frozenset[str] = frozenset({"Protocol", "ABC", "TypedDict"})


def _is_contract_class(node: ast.ClassDef) -> bool:
    for base in node.bases:
        name = _dotted_of(base)
        if name and name.split(".")[-1] in _CONTRACT_BASES:
            return True
    for deco in node.decorator_list:
        name = _dotted_of(deco if not isinstance(deco, ast.Call) else deco.func)
        if name and name.split(".")[-1] == "runtime_checkable":
            return True
    return False


def _scan_pkg_for_contracts(pkg_root: Path) -> set[str]:
    out: set[str] = set()
    for path in _iter_src_py(pkg_root):
        tree = _parse_cached(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and _is_contract_class(node):
                out.add(node.name)
    return out


def collect_pkg_contract_classes(pkg_root: Path) -> set[str]:
    """Contract classes (Protocol/ABC/TypedDict) in *pkg_root* and sibling packages."""
    out: set[str] = _scan_pkg_for_contracts(pkg_root)

    parent = pkg_root.parent
    if parent.name == "packages" and parent.exists():
        for sibling in parent.iterdir():
            if not sibling.is_dir() or sibling == pkg_root:
                continue
            out |= _scan_pkg_for_contracts(sibling)

    axm_core = (
        pkg_root.parent.parent.parent / "axm-nexus" / "packages" / "axm"
        if parent.name == "packages"
        else None
    )
    if axm_core is not None and axm_core.exists():
        out |= _scan_pkg_for_contracts(axm_core)

    return out


# ── Tautology / smoke-test heuristics ─────────────────────────────────


def _is_docstring_stmt(stmt: ast.stmt) -> bool:
    return (
        isinstance(stmt, ast.Expr)
        and isinstance(stmt.value, ast.Constant)
        and isinstance(stmt.value.value, str)
    )


def _is_is_not_none_compare(test: ast.Compare) -> bool:
    return (
        len(test.ops) == 1
        and isinstance(test.ops[0], ast.IsNot)
        and len(test.comparators) == 1
        and isinstance(test.comparators[0], ast.Constant)
        and test.comparators[0].value is None
    )


def _is_weak_assert(stmt: ast.stmt) -> bool | None:
    if isinstance(stmt, ast.Assert):
        test = stmt.test
        if isinstance(test, ast.Name):
            return True
        if isinstance(test, ast.Compare):
            return _is_is_not_none_compare(test)
        if isinstance(test, ast.Call) and isinstance(test.func, ast.Name):
            return test.func.id in ("isinstance", "callable")
        return False
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
        call = stmt.value
        return (
            isinstance(call.func, ast.Attribute) and call.func.attr == "assertIsNotNone"
        )
    return None


_SmokeStmtKind = Literal["import", "weak", "strong", "other"]


def _classify_smoke_stmt(stmt: ast.stmt) -> _SmokeStmtKind:
    if isinstance(stmt, ast.Import | ast.ImportFrom):
        return "import"
    weak = _is_weak_assert(stmt)
    if weak is None:
        return "other"
    return "weak" if weak else "strong"


def is_import_smoke_test(func: ast.FunctionDef) -> bool:
    """Detect an import + weak-assert smoke test.

    Returns True when the function body (docstrings excluded, ≤ 4 stmts)
    contains at least one ``import``/``from … import …`` statement and at
    least one weak assertion (``assert name``, ``assert x is not None``,
    ``assert isinstance(...)``, ``assert callable(...)``, or
    ``self.assertIsNotNone(...)``), with no statement stronger than these.
    """
    body = [s for s in func.body if not _is_docstring_stmt(s)]
    if len(body) > _SMOKE_BODY_BUDGET:
        return False
    kinds = {_classify_smoke_stmt(stmt) for stmt in body}
    return "import" in kinds and "weak" in kinds and not (kinds & {"strong", "other"})


def _has_lazy_filename(test_file: Path) -> bool:
    return Path(test_file).name.lower() in _LAZY_FILENAMES


def _has_lazy_classname(func: ast.FunctionDef, tree_module: ast.Module) -> bool:
    for node in ast.walk(tree_module):
        if not isinstance(node, ast.ClassDef):
            continue
        if not any(item is func for item in node.body):
            continue
        cname = node.name.lower()
        if any(sig in cname for sig in _LAZY_CLASSNAME_SIGNALS):
            return True
    return False


def _has_lazy_module_docstring(tree_module: ast.Module) -> bool:
    if not tree_module.body or not _is_docstring_stmt(tree_module.body[0]):
        return False
    first = tree_module.body[0]
    assert isinstance(first, ast.Expr)
    assert isinstance(first.value, ast.Constant)
    value = first.value.value
    if not isinstance(value, str):
        return False
    doc = value.lower()
    return any(sig in doc for sig in _LAZY_DOCSTRING_SIGNALS)


def test_is_in_lazy_import_context(
    func: ast.FunctionDef,
    tree_module: ast.Module,
    test_file: Path,
) -> bool:
    """Detect when the import itself is the system-under-test.

    Returns True when the surrounding test file, class, or module
    docstring signals that the test exists to verify lazy/optional
    imports — in which case bare ``import`` statements inside the
    test body must not be flagged as smoke tests.
    """
    return (
        _has_lazy_filename(test_file)
        or _has_lazy_classname(func, tree_module)
        or _has_lazy_module_docstring(tree_module)
    )


# ── Mock extraction ───────────────────────────────────────────────────


def _dotted_of(expr: ast.AST) -> str | None:
    parts: list[str] = []
    cur: ast.AST = expr
    while True:
        if isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        elif isinstance(cur, ast.Name):
            parts.append(cur.id)
            break
        else:
            return None
    return ".".join(reversed(parts))


_STRING_ARG_KINDS = frozenset(
    {"patch", "patch.dict", "monkeypatch.setenv", "monkeypatch.delenv"}
)


_PATCH_KIND_SUFFIXES: tuple[tuple[str, str], ...] = (
    ("patch.object", "patch.object"),
    ("patch.dict", "patch.dict"),
    ("monkeypatch.setattr", "monkeypatch.setattr"),
    ("monkeypatch.setenv", "monkeypatch.setenv"),
    ("monkeypatch.delenv", "monkeypatch.delenv"),
    ("patch", "patch"),
)


def _classify_patch_kind(call: ast.Call) -> str | None:
    qual = _dotted_of(call.func)
    if not qual:
        return None
    for suffix, kind in _PATCH_KIND_SUFFIXES:
        if qual == suffix or qual.endswith(f".{suffix}"):
            return kind
    if qual.endswith(".setattr") and "monkeypatch" in qual:
        return "monkeypatch.setattr"
    return None


def _append_string_arg_target(call: ast.Call, out: list[str]) -> None:
    first = call.args[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        out.append(first.value)
    elif isinstance(first, ast.JoinedStr):
        for value in first.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                out.append(value.value)


def _append_object_attr_target(call: ast.Call, out: list[str]) -> None:
    first = call.args[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        out.append(first.value)
        return
    attr_node = call.args[1] if len(call.args) >= _SETATTR_OBJ_FORM_MIN_ARGS else None
    if not (isinstance(attr_node, ast.Constant) and isinstance(attr_node.value, str)):
        return
    obj_name = _dotted_of(first) or ""
    if obj_name:
        out.append(f"{obj_name}.{attr_node.value}")
    else:
        out.append(attr_node.value)


def _patch_call_targets(call: ast.Call, out: list[str]) -> None:
    kind = _classify_patch_kind(call)
    if kind is None or not call.args:
        return
    if kind in _STRING_ARG_KINDS:
        _append_string_arg_target(call, out)
    else:
        _append_object_attr_target(call, out)


def extract_mock_targets(func: ast.FunctionDef) -> list[str]:
    """Collect dotted mock/patch targets + ``mock-factory:Mock/...`` markers."""
    out: list[str] = []
    for node in ast.walk(func):
        if not isinstance(node, ast.Call):
            continue
        _patch_call_targets(node, out)
        qual = _dotted_of(node.func) or ""
        leaf = qual.rsplit(".", 1)[-1] if qual else ""
        if leaf in _MOCK_FACTORIES:
            out.append(f"mock-factory:{leaf}")
    return out


def target_matches_io(target: str) -> bool:
    """Return ``True`` when ``target`` references a known I/O call or module.

    Args:
        target: Dotted call expression captured from the AST (e.g.
            ``pathlib.Path.read_text``).

    Returns:
        ``True`` when the leaf call name, the full dotted target, or any of
        its dotted segments matches the package's I/O catalog; ``False``
        otherwise (including for empty input).
    """
    if not target:
        return False
    if target in _IO_CALLS:
        return True
    for call in _IO_CALLS:
        if target.endswith("." + call):
            return True
    leaf_io_mods = {m.split(".")[-1] for m in _IO_MODULES}
    tokens = target.split(".")
    return any(tok in leaf_io_mods for tok in tokens)


# ── In-package script detection ───────────────────────────────
#
# `load_project_scripts` and `has_in_package_subprocess_invocation` are the
# single source of truth for the ``[project.scripts]`` + argv heuristic.
# ``pyramid_level`` and ``no_package_symbol`` both import these helpers.
# Tightening the argv reconstruction would regress PYRAMID findings on
# ``axm-audit`` (AXM-1720) — keep the permissive contract intact.


def load_project_scripts(pkg_root: Path) -> set[str]:
    """Return scripts declared by ``[project.scripts]`` in pyproject.toml."""
    pyproject = pkg_root / "pyproject.toml"
    if not pyproject.exists():
        return set()
    with pyproject.open("rb") as handle:
        data = tomllib.load(handle)
    scripts = data.get("project", {}).get("scripts", {})
    if not isinstance(scripts, dict):
        return set()
    return {name for name in scripts if isinstance(name, str)}


def has_in_package_subprocess_invocation(
    *,
    call: ast.Call,
    module_ast: ast.Module,
    project_scripts: set[str],
) -> bool:
    """Return true when *call* invokes a declared package script."""
    if not project_scripts:
        return False
    argv = _argv_from_call(call, module_ast)
    if argv is None:
        return False
    return _argv_contains_package_entrypoint(argv, project_scripts)


def _script_module_aliases(project_scripts: set[str]) -> set[str]:
    return {script.replace("-", "_") for script in project_scripts}


def _argv_contains_package_entrypoint(
    argv: list[str], project_scripts: set[str]
) -> bool:
    module_aliases = _script_module_aliases(project_scripts)
    for index, arg in enumerate(argv):
        if arg in project_scripts:
            return True
        if arg == "-m" and index + 1 < len(argv):
            module = argv[index + 1]
            if any(
                module == alias or module.startswith(f"{alias}.")
                for alias in module_aliases
            ):
                return True
    return False


def _module_string_constants(module_ast: ast.Module) -> dict[str, str]:
    constants: dict[str, str] = {}
    for stmt in module_ast.body:
        if isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Constant):
            if not isinstance(stmt.value.value, str):
                continue
            for target in stmt.targets:
                if isinstance(target, ast.Name):
                    constants[target.id] = stmt.value.value
    return constants


def _enclosing_function(
    module_ast: ast.Module, call: ast.Call
) -> ast.FunctionDef | None:
    for node in ast.walk(module_ast):
        end_lineno = getattr(node, "end_lineno", None)
        if (
            isinstance(node, ast.FunctionDef)
            and end_lineno is not None
            and node.lineno <= call.lineno <= end_lineno
        ):
            return node
    return None


def _local_string_constants(func: ast.FunctionDef, call: ast.Call) -> dict[str, str]:
    constants: dict[str, str] = {}
    for stmt in func.body:
        if getattr(stmt, "lineno", 0) >= call.lineno:
            break
        if (
            isinstance(stmt, ast.Assign)
            and isinstance(stmt.value, ast.Constant)
            and isinstance(stmt.value.value, str)
        ):
            for target in stmt.targets:
                if isinstance(target, ast.Name):
                    constants[target.id] = stmt.value.value
    return constants


def _local_list_bindings(
    func: ast.FunctionDef, call: ast.Call, constants: dict[str, str]
) -> dict[str, list[str]]:
    bindings: dict[str, list[str]] = {}
    for stmt in func.body:
        if getattr(stmt, "lineno", 0) >= call.lineno:
            break
        if isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.List):
            argv = _argv_from_list(stmt.value, constants)
            for target in stmt.targets:
                if isinstance(target, ast.Name):
                    bindings[target.id] = argv
    return bindings


def _argv_from_call(call: ast.Call, module_ast: ast.Module) -> list[str] | None:
    if not call.args:
        return None
    constants = _module_string_constants(module_ast)
    func = _enclosing_function(module_ast, call)
    list_bindings: dict[str, list[str]] = {}
    if func is not None:
        constants |= _local_string_constants(func, call)
        list_bindings = _local_list_bindings(func, call, constants)
    arg = call.args[0]
    if isinstance(arg, ast.List):
        return _argv_from_list(arg, constants)
    if isinstance(arg, ast.Name):
        return list_bindings.get(arg.id)
    return None


def _argv_from_list(node: ast.List, constants: dict[str, str]) -> list[str]:
    """Reconstruct a best-effort argv from an ``ast.List`` literal.

    Non-resolvable elements (e.g. ``str(tmp_path)``, f-strings, attribute
    accesses other than ``sys.executable``) are skipped rather than aborting
    the whole reconstruction — downstream consumers match on string equality
    over the resolved tokens, so partial argvs are still useful.
    """
    argv: list[str] = []
    for item in node.elts:
        if isinstance(item, ast.Constant) and isinstance(item.value, str):
            argv.append(item.value)
        elif isinstance(item, ast.Name) and item.id in constants:
            argv.append(constants[item.id])
        elif (
            isinstance(item, ast.Attribute)
            and isinstance(item.value, ast.Name)
            and item.value.id == "sys"
            and item.attr == "executable"
        ):
            argv.append("python")
    return argv


# ── First-party symbol detection ──────────────────────────────
#
# Helpers ported from `scripts/test_orga/tuple_naming_proto.py` (functions
# `_collect_package_imports`, `_used_names_in_node`, `_closure_nodes_for_test`,
# `_resolve_fixture_symbol`). They power criterion (a) of the
# TEST_QUALITY_NO_PACKAGE_SYMBOL rule.


def _aliases_from_import_from(
    node: ast.ImportFrom, pkg_prefixes: set[str]
) -> dict[str, str]:
    """``from pkg.x import y`` → ``{y: 'pkg.x.y'}`` when ``pkg`` is first-party."""
    mod = node.module or ""
    if mod.split(".", 1)[0] not in pkg_prefixes:
        return {}
    return {(alias.asname or alias.name): f"{mod}.{alias.name}" for alias in node.names}


def _aliases_from_import(node: ast.Import, pkg_prefixes: set[str]) -> dict[str, str]:
    """``import pkg.x as y`` → ``{y: 'pkg.x'}`` when ``pkg`` is first-party."""
    out: dict[str, str] = {}
    for alias in node.names:
        if alias.name.split(".", 1)[0] not in pkg_prefixes:
            continue
        local = alias.asname or alias.name.split(".")[0]
        out[local] = alias.name
    return out


def _collect_first_party_aliases(
    tree: ast.AST, pkg_prefixes: set[str]
) -> dict[str, str]:
    """Return ``{local_name: dotted_origin}`` for every first-party import."""
    if not pkg_prefixes:
        return {}
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            aliases.update(_aliases_from_import_from(node, pkg_prefixes))
        elif isinstance(node, ast.Import):
            aliases.update(_aliases_from_import(node, pkg_prefixes))
    return aliases


def _module_level_funcs_by_name(tree: ast.Module) -> dict[str, ast.FunctionDef]:
    return {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}


def _module_level_classes_by_name(tree: ast.Module) -> dict[str, ast.ClassDef]:
    return {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}


def _direct_callee_names(node: ast.AST) -> set[str]:
    callees: set[str] = set()
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Call):
            continue
        func = sub.func
        if isinstance(func, ast.Name):
            callees.add(func.id)
        elif isinstance(func, ast.Attribute):
            callees.add(func.attr)
    return callees


def _referenced_class_names_in(
    nodes: list[ast.AST],
    mod_classes: dict[str, ast.ClassDef],
) -> set[str]:
    """Collect names of module-level classes referenced inside *nodes*."""
    names: set[str] = set()
    for n in nodes:
        for sub in ast.walk(n):
            if isinstance(sub, ast.Name) and sub.id in mod_classes:
                names.add(sub.id)
    return names


def _seed_visit_list(
    test_func: ast.FunctionDef,
    mod_funcs: dict[str, ast.FunctionDef],
) -> list[str]:
    """Return the initial work-list for the intra-module call-graph walk."""
    if test_func.name in mod_funcs:
        return [test_func.name]
    return [c for c in _direct_callee_names(test_func) if c in mod_funcs]


def _walk_call_graph(
    seed: list[str], mod_funcs: dict[str, ast.FunctionDef]
) -> set[str]:
    """Return the set of module-level helper names reachable from *seed*."""
    seen: set[str] = set()
    work = list(seed)
    while work:
        name = work.pop()
        if name in seen or name not in mod_funcs:
            continue
        seen.add(name)
        for callee in _direct_callee_names(mod_funcs[name]):
            if callee in mod_funcs and callee not in seen:
                work.append(callee)
    return seen


def _closure_nodes_for_test(
    test_func: ast.FunctionDef,
    mod_funcs: dict[str, ast.FunctionDef],
    mod_classes: dict[str, ast.ClassDef],
) -> list[ast.AST]:
    """Return the test body + bodies of transitively-called module helpers.

    Mirrors `scripts/test_orga/tuple_naming_proto.py:_closure_nodes_for_test`:
    walks the intra-module call graph, includes top-level classes referenced
    by name (synthetic subclasses, etc.), and seeds the closure with helpers
    a method-style test directly calls. Top-level pytest fixtures consumed
    by the test as parameters are also seeded, so a fixture body that
    exercises the package counts toward the test. No cross-file resolution.
    """
    seed = _seed_visit_list(test_func, mod_funcs)
    for fixture_name in _consumed_fixture_names(test_func, mod_funcs):
        if fixture_name not in seed:
            seed.append(fixture_name)
    seen_funcs = _walk_call_graph(seed, mod_funcs)
    nodes: list[ast.AST] = [mod_funcs[n] for n in seen_funcs if n in mod_funcs]
    if test_func.name not in seen_funcs:
        nodes.append(test_func)
    for cname in _referenced_class_names_in(nodes, mod_classes):
        nodes.append(mod_classes[cname])
    return nodes


def _consumed_fixture_names(
    test_func: ast.FunctionDef,
    mod_funcs: dict[str, ast.FunctionDef],
) -> list[str]:
    """Return names of top-level pytest fixtures the test consumes by parameter."""
    params = _func_param_names(test_func)
    return [
        name
        for name in params
        if name in mod_funcs and _is_pytest_fixture_decorator(mod_funcs[name])
    ]


def _walk_touches_known(node: ast.AST, known: set[str]) -> bool:
    """True if any ``ast.Name`` or attribute root inside *node* is in *known*."""
    if not known:
        return False
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name) and sub.id in known:
            return True
        if isinstance(sub, ast.Attribute):
            root: ast.AST = sub
            while isinstance(root, ast.Attribute):
                root = root.value
            if isinstance(root, ast.Name) and root.id in known:
                return True
    return False


def _is_pytest_fixture_decorator(func: ast.FunctionDef) -> bool:
    for dec in func.decorator_list:
        target = dec.func if isinstance(dec, ast.Call) else dec
        if isinstance(target, ast.Name) and target.id == "fixture":
            return True
        if isinstance(target, ast.Attribute) and target.attr == "fixture":
            return True
    return False


def _attribute_root_id_if_known(node: ast.Attribute, known: set[str]) -> str | None:
    """Return the root ``ast.Name.id`` of an attribute chain if it is in *known*."""
    root: ast.AST = node
    while isinstance(root, ast.Attribute):
        root = root.value
    if isinstance(root, ast.Name) and root.id in known:
        return root.id
    return None


def _known_id_from_expr(node: ast.AST, known: set[str]) -> str | None:
    """Return the *known* identifier from a value expression, or ``None``."""
    value = node
    if isinstance(value, ast.Call):
        value = value.func
    if isinstance(value, ast.Name) and value.id in known:
        return value.id
    if isinstance(value, ast.Attribute):
        return _attribute_root_id_if_known(value, known)
    return None


def _resolve_return_annotation(returns: ast.AST | None, known: set[str]) -> str | None:
    """Map a ``-> X`` return annotation to a *known* alias, when applicable."""
    if isinstance(returns, ast.Name) and returns.id in known:
        return returns.id
    if isinstance(returns, ast.Attribute):
        return _attribute_root_id_if_known(returns, known)
    return None


def _returned_value(sub: ast.AST) -> ast.AST | None:
    """Return the value expression of ``return X`` / ``yield X`` nodes."""
    if isinstance(sub, ast.Return):
        return sub.value
    if isinstance(sub, ast.Expr) and isinstance(sub.value, ast.Yield):
        return sub.value.value
    return None


def _last_known_in_body(func: ast.FunctionDef, known: set[str]) -> str | None:
    """Return the last *known* alias appearing in a ``return``/``yield`` value."""
    candidate: str | None = None
    for sub in ast.walk(func):
        value = _returned_value(sub)
        if value is None:
            continue
        resolved = _known_id_from_expr(value, known)
        if resolved is not None:
            candidate = resolved
    return candidate


def _resolve_first_party_fixture_symbol(
    func: ast.FunctionDef, known: set[str]
) -> str | None:
    """Return the first-party alias this fixture yields/returns, if any.

    Resolution order (per ``tuple_naming_proto.py``):
        1. return-type annotation (``-> Rule``)
        2. last ``return X(...) | return X`` in the body
        3. last ``yield X(...) | yield X`` in the body
    Only names present in *known* (i.e. imported from a first-party package)
    are accepted.
    """
    hit = _resolve_return_annotation(func.returns, known)
    if hit is not None:
        return hit
    return _last_known_in_body(func, known)


def _collect_first_party_fixture_map(
    tree: ast.Module, known: set[str]
) -> dict[str, str]:
    """Return ``{fixture_name: first_party_alias}`` for top-level fixtures."""
    mapping: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and _is_pytest_fixture_decorator(node):
            sym = _resolve_first_party_fixture_symbol(node, known)
            if sym is not None:
                mapping[node.name] = sym
    return mapping


def _func_param_names(func: ast.FunctionDef) -> set[str]:
    args = func.args
    names: set[str] = {a.arg for a in args.args + args.kwonlyargs}
    if args.vararg:
        names.add(args.vararg.arg)
    if args.kwarg:
        names.add(args.kwarg.arg)
    return names


def test_references_first_party(
    *,
    test_func: ast.FunctionDef,
    module_ast: ast.Module,
    pkg_prefixes: set[str],
) -> bool:
    """True when *test_func* exercises a first-party Python symbol.

    Criterion (a) of the TEST_QUALITY_NO_PACKAGE_SYMBOL rule. A symbol is
    "exercised" if it is referenced anywhere in the intra-module closure
    of *test_func* (its body + bodies of every top-level helper it calls
    transitively), or indirectly via a fixture whose return-type annotation
    or return/yield expression resolves to a first-party alias.
    """
    aliases = _collect_first_party_aliases(module_ast, pkg_prefixes)
    if not aliases:
        return False
    known: set[str] = set(aliases)
    mod_funcs = _module_level_funcs_by_name(module_ast)
    mod_classes = _module_level_classes_by_name(module_ast)
    closure = _closure_nodes_for_test(test_func, mod_funcs, mod_classes)
    if any(_walk_touches_known(node, known) for node in closure):
        return True
    fixture_map = _collect_first_party_fixture_map(module_ast, known)
    if not fixture_map:
        return False
    params = _func_param_names(test_func)
    return any(name in params for name in fixture_map)


# Pytest sees the ``test_`` prefix and tries to collect these helpers when a
# test module imports them. The ``__test__ = False`` attribute is the
# documented opt-out (https://docs.pytest.org/en/stable/example/pythoncollection.html).
test_references_first_party.__test__ = False  # type: ignore[attr-defined]


# ── In-package CLI invocation ───────────────────────────────
#
# Criterion (b): the closure invokes a declared script via ``subprocess.run``
# or `CliRunner().invoke(app, [...])`. CliRunner support is single-binary
# only — multi-binary apps would require per-import tracking (see
# `scripts/test_orga/tuple_naming_e2e_proto.py:282-292`).


def _is_subprocess_call(call: ast.Call) -> bool:
    func = call.func
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        return func.value.id == "subprocess" and func.attr in {
            "run",
            "call",
            "check_call",
            "check_output",
            "Popen",
        }
    if isinstance(func, ast.Name):
        return func.id in {"run", "check_output", "check_call", "call", "Popen"}
    return False


def _is_clirunner_invoke_call(call: ast.Call) -> bool:
    return isinstance(call.func, ast.Attribute) and call.func.attr == "invoke"


def _calls_in_nodes(nodes: list[ast.AST]) -> Iterator[ast.Call]:
    seen: set[int] = set()
    for node in nodes:
        for sub in ast.walk(node):
            if isinstance(sub, ast.Call) and id(sub) not in seen:
                seen.add(id(sub))
                yield sub


def test_invokes_in_package_script(
    *,
    test_func: ast.FunctionDef,
    module_ast: ast.Module,
    project_scripts: set[str],
) -> bool:
    """True when the test's closure invokes a declared package script.

    Criterion (b) of TEST_QUALITY_NO_PACKAGE_SYMBOL. Recognises
    ``subprocess.run(["script", ...])`` (also ``python -m pkg ...``) and
    ``CliRunner().invoke(app, [...])`` shapes. The walk uses the same
    intra-module closure as criterion (a) so a helper-wrapped invocation
    still counts.
    """
    if not project_scripts:
        return False
    mod_funcs = _module_level_funcs_by_name(module_ast)
    mod_classes = _module_level_classes_by_name(module_ast)
    closure = _closure_nodes_for_test(test_func, mod_funcs, mod_classes)
    for call in _calls_in_nodes(closure):
        if _is_subprocess_call(call) and has_in_package_subprocess_invocation(
            call=call,
            module_ast=module_ast,
            project_scripts=project_scripts,
        ):
            return True
        if _is_clirunner_invoke_call(call) and call.args:
            return True
    return False


test_invokes_in_package_script.__test__ = False  # type: ignore[attr-defined]


# ── Canonical filename emission (FILE_NAMING) ─────────────────
#
# Helpers ported from ``scripts/test_orga/tuple_naming_proto.py`` and
# ``tuple_naming_e2e_proto.py``. They power TEST_QUALITY_FILE_NAMING: count
# first-party symbol usage and CLI invocations in a test body (no closure
# walk), then emit the canonical ``test_{tuple}.py`` filename.

_FILE_NAMING_TOP_K = 2


def to_snake_token(name: str) -> str:
    """Normalize a PascalCase / kebab-case token to snake_case.

    Used to compose canonical filenames. Empty input returns empty.
    """
    if not name:
        return name
    name = name.replace("-", "_")
    out: list[str] = []
    for i, ch in enumerate(name):
        if (
            ch.isupper()
            and i > 0
            and (name[i - 1].islower() or (i + 1 < len(name) and name[i + 1].islower()))
        ):
            out.append("_")
        out.append(ch.lower())
    return "".join(out).lstrip("_")


def _ref_name(node: ast.AST) -> str | None:
    """Return the bound name for an ``ast.Name`` / ``ast.Attribute`` root."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        root: ast.AST = node
        while isinstance(root, ast.Attribute):
            root = root.value
        if isinstance(root, ast.Name):
            return root.id
    return None


def first_party_symbol_counts(
    *,
    test_func: ast.FunctionDef,
    mod_ast: ast.Module,
    pkg_prefixes: set[str],
) -> Counter[str]:
    """Count direct references to first-party symbols inside *test_func*.

    Aliases are resolved from the module's imports (``from pkg.x import Y``
    or ``import pkg.x as y``). Per the FILE_NAMING design, only the bare
    test body is walked — no helper closure — because tuple emission must
    reflect direct usage frequency, not transitive reachability.
    """
    aliases = _collect_first_party_aliases(mod_ast, pkg_prefixes)
    if not aliases:
        return Counter()
    known = set(aliases)
    counts: Counter[str] = Counter()
    for sub in ast.walk(test_func):
        name = _ref_name(sub) if isinstance(sub, (ast.Name, ast.Attribute)) else None
        if name is not None and name in known:
            counts[name] += 1
    return counts


def _has_shell_true(call: ast.Call) -> bool:
    """Return True if *call* has ``shell=True`` among its keywords."""
    return any(
        kw.arg == "shell"
        and isinstance(kw.value, ast.Constant)
        and kw.value.value is True
        for kw in call.keywords
    )


def _match_script_in_argv(
    argv: list[str],
    project_scripts: set[str],
    script_modules: dict[str, str],
) -> tuple[str, str] | None:
    """Find the first project-script match in *argv*.

    Return ``(script, sub_cmd)`` or *None*.
    """
    match_idx: int | None = None
    match_script: str | None = None
    for i, tok in enumerate(argv):
        if tok in project_scripts:
            match_idx, match_script = i, tok
            break
        if tok in script_modules:
            match_idx, match_script = i, script_modules[tok]
            break
    if match_idx is None or match_script is None:
        return None
    sub_cmd = ""
    sub_idx = match_idx + 1
    if len(argv) > sub_idx and not argv[sub_idx].startswith("-"):
        sub_cmd = argv[sub_idx]
    return match_script, sub_cmd


def cli_invocation_tuple(
    *,
    test_func: ast.FunctionDef,
    mod_ast: ast.Module,
    project_scripts: set[str],
) -> Counter[tuple[str, str]]:
    """Count ``(bin, sub)`` invocations of declared scripts in *test_func*.

    Recognises ``subprocess.run(["bin", "sub", ...])`` shapes (including
    module aliases like ``python -m pkg ...`` and indirect list/string
    bindings already handled by ``_argv_from_call``). The sub-command is the
    first non-flag argv element after the matched binary, or ``""`` when the
    bare binary is invoked. Non-package invocations (``git init``,
    ``shutil.which``-resolved plumbing) yield an empty counter.
    """
    if not project_scripts:
        return Counter()
    counts: Counter[tuple[str, str]] = Counter()
    script_modules = {s.replace("-", "_"): s for s in project_scripts}
    for sub in ast.walk(test_func):
        if not isinstance(sub, ast.Call) or not _is_subprocess_call(sub):
            continue
        if _has_shell_true(sub):
            continue
        argv = _argv_from_call(sub, mod_ast)
        if not argv:
            continue
        result = _match_script_in_argv(argv, project_scripts, script_modules)
        if result is not None:
            counts[result] += 1
    return counts


def canonical_filename(
    *,
    symbols_or_tuples: object,
    tier: str,
    single_binary: str | None,
) -> str:
    """Emit the canonical ``test_*.py`` filename for a tier's tuple.

    For ``tier="integration"``, *symbols_or_tuples* is an iterable of
    first-party symbol names; the top-K=2 (already sorted) are snake-cased
    and joined by ``__`` (PEP 8 module name; a single ``-`` would break
    Python imports). For ``tier="e2e"``, *symbols_or_tuples* is an iterable
    of ``(bin, sub)`` tuples; the same K=2 rule applies. When *single_binary*
    is not None, the redundant binary prefix is stripped: ``(axm-audit,
    audit)`` emits ``test_audit.py``; ``(axm-audit, "")`` emits the bare
    binary ``test_axm_audit.py``.

    K=0 yields ``test_UNKNOWN.py`` — but the FILE_NAMING rule never emits
    K=0 findings (that case is NO_PACKAGE_SYMBOL's concern).
    """
    items = list(symbols_or_tuples)  # type: ignore[call-overload]
    if not items:
        return "test_UNKNOWN.py"
    if tier == "e2e":
        tokens = _e2e_tokens(items, single_binary)
    else:
        tokens = sorted({to_snake_token(s) for s in items if s})[:_FILE_NAMING_TOP_K]
    if not tokens:
        return "test_UNKNOWN.py"
    # Join tokens with ``__`` (PEP 8 module name) rather than ``-``: a
    # dash is invalid in Python identifiers, which breaks
    # ``from tests.<tier>.test_a-b import *`` re-exports (a real pattern
    # used to satisfy PRACTICE_TEST_MIRROR) and IDE module navigation.
    # ``importlib`` mode lets pytest *collect* dash files, but Python
    # imports of those modules still raise SyntaxError.
    return "test_" + "__".join(tokens) + ".py"


def _e2e_tokens(
    items: list[tuple[str, str]],
    single_binary: str | None,
) -> list[str]:
    """Build the snake-cased ``__``-joined tokens for an e2e canonical name.

    When ``single_binary`` is set, the binary prefix is stripped: each
    ``(bin, sub)`` collapses to ``sub`` (or to ``bin`` if no sub is set,
    so a bare-binary invocation still surfaces a name).
    """
    if single_binary is not None:
        collapsed: list[str] = []
        for bin_name, sub in items[:_FILE_NAMING_TOP_K]:
            token = sub if sub else bin_name
            collapsed.append(to_snake_token(token))
        seen: set[str] = set()
        ordered: list[str] = []
        for tok in collapsed:
            if tok and tok not in seen:
                seen.add(tok)
                ordered.append(tok)
        return ordered
    pieces: list[str] = []
    for bin_name, sub in items[:_FILE_NAMING_TOP_K]:
        bin_tok = to_snake_token(bin_name)
        sub_tok = to_snake_token(sub) if sub else ""
        # ``__`` (not ``-``) — see ``canonical_filename`` comment above.
        pieces.append(f"{bin_tok}__{sub_tok}" if sub_tok else bin_tok)
    return pieces
