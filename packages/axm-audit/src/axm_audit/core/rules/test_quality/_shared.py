"""Shared AST primitives for ``test_quality`` rules.

Registry-neutral helpers ported from the ``detect_pyramid_level_v6`` and
``triage_tautologies_v4`` prototypes.  Rules in this subpackage import
from here; no ``@register_rule`` lives here.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

from axm_audit.core.rules._helpers import get_ast_cache, parse_file_safe

__all__ = [
    "analyze_imports",
    "collect_pkg_contract_classes",
    "collect_pkg_public_symbols",
    "current_level_from_path",
    "detect_real_io",
    "extract_mock_targets",
    "fixture_does_io",
    "func_attr_io_transitive",
    "get_init_all",
    "get_module_all",
    "get_pkg_prefixes",
    "is_import_smoke_test",
    "iter_test_files",
    "target_matches_io",
    "test_is_in_lazy_import_context",
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

_FIXTURE_MOCK_PREFIXES: tuple[str, ...] = ("mock_", "fake_", "stub_")
_FIXTURE_MOCK_SUBSTRS: tuple[str, ...] = ("mock", "fake", "stub")

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
    src_dir = pkg_root / "src"
    if not src_dir.exists():
        return set()
    return {
        d.name for d in src_dir.iterdir() if d.is_dir() and not d.name.startswith(".")
    }


def _extract_all_from_tree(tree: ast.Module) -> set[str] | None:
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    return _literal_strings(node.value)
        if isinstance(node, ast.AugAssign):
            if isinstance(node.target, ast.Name) and node.target.id == "__all__":
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


def analyze_imports(  # noqa: PLR0912
    tree: ast.Module,
    pkg_prefixes: set[str],
    init_all: set[str] | None,
    pkg_root: Path,
) -> tuple[list[str], list[str], list[str], bool, set[str], list[str]]:
    """Classify imports + collect IO module names.

    Returns ``(public, internal, modules, has_private, io_module_names,
    io_signals)``.
    """
    public: list[str] = []
    internal: list[str] = []
    import_modules: list[str] = []
    has_private = False
    io_module_names: set[str] = set()
    io_signals: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            mod = node.module
            if mod in _IO_MODULES or any(mod.startswith(m + ".") for m in _IO_MODULES):
                io_signals.append(f"imports {mod}")
                for alias in node.names or []:
                    io_module_names.add(alias.asname or alias.name)
                continue

            is_pkg = any(mod == p or mod.startswith(p + ".") for p in pkg_prefixes)
            if not is_pkg:
                continue
            if mod not in import_modules:
                import_modules.append(mod)

            mod_all = get_module_all(pkg_root, mod)
            for alias in node.names or []:
                name = alias.name
                if name.startswith("_") and not (
                    name.startswith("__") and name.endswith("__")
                ):
                    has_private = True
                    internal.append(name)
                    continue
                in_root_all = init_all is not None and name in init_all
                in_mod_all = mod_all is not None and name in mod_all
                if in_root_all or in_mod_all:
                    public.append(name)
                else:
                    internal.append(name)

        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in _IO_MODULES:
                    io_signals.append(f"imports {alias.name}")
                    io_module_names.add(alias.asname or alias.name.split(".")[0])

    return public, internal, import_modules, has_private, io_module_names, io_signals


# ── IO detection ──────────────────────────────────────────────────────


def _attr_signals_in_node(node: ast.AST) -> list[str]:
    sigs: list[str] = []
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        if isinstance(child.func, ast.Attribute) and child.func.attr in _IO_ATTRS:
            sigs.append(f"attr:.{child.func.attr}()")
        if isinstance(child.func, ast.Name) and child.func.id == "open":
            sigs.append("call:open()")
    return sigs


def _names_called_in(node: ast.AST) -> set[str]:
    out: set[str] = set()
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        func = child.func
        if isinstance(func, ast.Name):
            out.add(func.id)
        elif isinstance(func, ast.Attribute):
            cur: ast.AST = func
            while isinstance(cur, ast.Attribute):
                cur = cur.value
            if isinstance(cur, ast.Name):
                out.add(cur.id)
    return out


def detect_real_io(tree: ast.Module) -> tuple[bool, bool, list[str]]:  # noqa: PLR0912
    """File-scope I/O detection (fixtures, calls, CLI runners) — no attr-IO."""
    has_io = False
    has_subprocess = False
    signals: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            for arg in node.args.args:
                if arg.arg in _IO_FIXTURES:
                    has_io = True
                    signals.append(f"fixture:{arg.arg}")

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        if isinstance(node.func, ast.Attribute):
            parts: list[str] = []
            cur: ast.AST = node.func
            while isinstance(cur, ast.Attribute):
                parts.insert(0, cur.attr)
                cur = cur.value
            if isinstance(cur, ast.Name):
                parts.insert(0, cur.id)
                full = ".".join(parts)
                if full in _IO_CALLS:
                    has_io = True
                    signals.append(f"call:{full}")
                    if full.startswith("subprocess."):
                        has_subprocess = True

        if isinstance(node.func, ast.Attribute) and node.func.attr == "invoke":
            target = node.func.value
            if isinstance(target, ast.Call) and isinstance(target.func, ast.Name):
                if target.func.id in _CLI_RUNNER_CLASSES:
                    has_subprocess = True
                    has_io = True
                    signals.append(f"cli:{target.func.id}")
            if isinstance(target, ast.Name) and target.id in _CLI_RUNNER_NAMES:
                has_subprocess = True
                has_io = True
                signals.append(f"cli:{target.id}")

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


def _load_conftest_fixtures(conftest: Path) -> dict[str, ast.FunctionDef]:
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


def fixture_does_io(  # noqa: PLR0911, PLR0912
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

    if _attr_signals_in_node(fdef):
        return True

    for node in ast.walk(fdef):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Attribute):
            parts: list[str] = []
            cur: ast.AST = node.func
            while isinstance(cur, ast.Attribute):
                parts.insert(0, cur.attr)
                cur = cur.value
            if isinstance(cur, ast.Name):
                parts.insert(0, cur.id)
                if ".".join(parts) in _IO_CALLS:
                    return True

    for arg in fdef.args.args:
        if arg.arg in ("tmp_path", "tmp_path_factory"):
            if _expr_contains_names(fdef, {arg.arg}):
                return True
        if arg.arg in fixtures and arg.arg != fix_name:
            if fixture_does_io(arg.arg, fixtures, visited, depth + 1):
                return True

    return False


# ── Package surface ───────────────────────────────────────────────────


def _iter_src_py(pkg_root: Path) -> Iterator[Path]:
    src = pkg_root / "src"
    if not src.exists():
        return
    yield from sorted(src.rglob("*.py"))


def collect_pkg_public_symbols(pkg_root: Path) -> set[str]:
    """Top-level function / class / constant names across ``src/``."""
    out: set[str] = set()
    for path in _iter_src_py(pkg_root):
        tree = _parse_cached(path)
        if tree is None:
            continue
        for node in tree.body:
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                if not node.name.startswith("_"):
                    out.add(node.name)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and not target.id.startswith("_"):
                        out.add(target.id)
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                if not node.target.id.startswith("_"):
                    out.add(node.target.id)
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


def is_import_smoke_test(func: ast.FunctionDef) -> bool:
    """Docstring-aware import + weak-assert smoke pattern (body ≤ 4 stmts)."""
    body = [s for s in func.body if not _is_docstring_stmt(s)]
    if len(body) > _SMOKE_BODY_BUDGET:
        return False
    has_import = False
    has_any_assert = False
    has_only_weak = True
    for stmt in body:
        if isinstance(stmt, ast.Import | ast.ImportFrom):
            has_import = True
            continue
        if isinstance(stmt, ast.Assert):
            has_any_assert = True
            test = stmt.test
            if isinstance(test, ast.Compare):
                if (
                    len(test.ops) == 1
                    and isinstance(test.ops[0], ast.IsNot)
                    and len(test.comparators) == 1
                    and isinstance(test.comparators[0], ast.Constant)
                    and test.comparators[0].value is None
                ):
                    continue
            if isinstance(test, ast.Name):
                continue
            if (
                isinstance(test, ast.Call)
                and isinstance(test.func, ast.Name)
                and test.func.id in ("isinstance", "callable")
            ):
                continue
            has_only_weak = False
        elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            call = stmt.value
            if (
                isinstance(call.func, ast.Attribute)
                and call.func.attr == "assertIsNotNone"
            ):
                has_any_assert = True
                continue
            has_only_weak = False
        else:
            has_only_weak = False
    return has_import and has_any_assert and has_only_weak


def test_is_in_lazy_import_context(
    func: ast.FunctionDef,
    tree_module: ast.Module,
    test_file: Path,
) -> bool:
    """Detect when the import itself is the system-under-test."""
    fname = Path(test_file).name.lower()
    if fname in _LAZY_FILENAMES:
        return True

    for node in ast.walk(tree_module):
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item is func:
                    cname = node.name.lower()
                    if any(sig in cname for sig in _LAZY_CLASSNAME_SIGNALS):
                        return True

    if tree_module.body and _is_docstring_stmt(tree_module.body[0]):
        first = tree_module.body[0]
        assert isinstance(first, ast.Expr)
        assert isinstance(first.value, ast.Constant)
        doc = first.value.value.lower()
        if any(sig in doc for sig in _LAZY_DOCSTRING_SIGNALS):
            return True

    return False


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


def _patch_call_targets(call: ast.Call, out: list[str]) -> None:  # noqa: PLR0912
    qual = _dotted_of(call.func)
    if not qual:
        return
    kind: str | None = None
    if qual == "patch" or qual.endswith(".patch"):
        kind = "patch"
    elif qual == "patch.object" or qual.endswith(".patch.object"):
        kind = "patch.object"
    elif qual == "patch.dict" or qual.endswith(".patch.dict"):
        kind = "patch.dict"
    elif qual.endswith("monkeypatch.setattr") or (
        qual.endswith(".setattr") and "monkeypatch" in qual
    ):
        kind = "monkeypatch.setattr"
    elif qual.endswith("monkeypatch.setenv"):
        kind = "monkeypatch.setenv"
    elif qual.endswith("monkeypatch.delenv"):
        kind = "monkeypatch.delenv"
    else:
        return

    if not call.args:
        return
    first = call.args[0]
    if kind in ("patch", "patch.dict", "monkeypatch.setenv", "monkeypatch.delenv"):
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            out.append(first.value)
        elif isinstance(first, ast.JoinedStr):
            for value in first.values:
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    out.append(value.value)
        return

    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        out.append(first.value)
        return
    attr_node = call.args[1] if len(call.args) >= _SETATTR_OBJ_FORM_MIN_ARGS else None
    obj_name = _dotted_of(first) or ""
    if isinstance(attr_node, ast.Constant) and isinstance(attr_node.value, str):
        if obj_name:
            out.append(f"{obj_name}.{attr_node.value}")
        else:
            out.append(attr_node.value)


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
