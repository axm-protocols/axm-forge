"""Read-only AST inspection: tests, classes, imports, helpers, markers.

All helpers operate on ``ast.Module`` / ``ast.stmt`` nodes from the stdlib
``ast`` module — no libcst, no mutation, no I/O beyond ``Path.read_text``
when an entry point takes a path. This file gathers every read-side AST
primitive used by the fix pipeline so that ``cst_rewrite`` / ``stages_*``
can stay focused on side-effects.

Future: the higher-level pieces (``top_level_test_classes``,
``top_level_helpers``, ``collect_imported_names``) may move to
``axm-ast`` once that package exposes raw ``ast.Module`` access. The
fine-grained walkers (``class_is_pathological``, ``marker_fixtures_in_unit``)
are too specific to pytest semantics to belong in a general lib.
"""

from __future__ import annotations

import ast
import hashlib
from collections import deque
from collections.abc import Iterator
from pathlib import Path

__all__ = [
    "_BUILTINS",
    "_collect_conftest_fixtures",
    "_collect_defined_names",
    "_collect_marker_fixtures_to_move",
    "_collect_module_level_deps_to_copy",
    "_collect_referenced_names",
    "_decorator_free_names",
    "_seed_module_deps_from_units",
    "_source_top_level_definitions",
    "_stmt_assignment_targets",
    "_const_value_hash",
    "_helper_body_hash",
    "_is_pytest_fixture",
    "_movable_units_at_top_level",
    "_names_referenced_in_unit",
    "_references_file_dunder",
    "_source_segment_with_decorators",
    "_string_literal_fixtures_in_unit",
    "_top_level_test_names",
    "_walk_test_funcs",
    "class_is_pathological",
    "collect_imported_names",
    "file_has_pathological_class",
    "func_body_hash",
    "marker_fixtures_in_unit",
    "top_level_helpers",
    "top_level_test_classes",
]


_BUILTINS = set(
    dir(__builtins__) if isinstance(__builtins__, dict) else dir(__builtins__)
)


# ---------------------------------------------------------------------------
# Tests + classes
# ---------------------------------------------------------------------------


def _walk_test_funcs(tree: ast.Module) -> list[ast.FunctionDef]:
    """Return test_* funcs at module level and inside Test* classes."""
    funcs: list[ast.FunctionDef] = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            funcs.append(node)
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            for child in node.body:
                if isinstance(child, ast.FunctionDef) and child.name.startswith(
                    "test_"
                ):
                    funcs.append(child)
    return funcs


def _top_level_test_names(tree: ast.Module) -> set[str]:
    """test_* function names at module level only (no class methods)."""
    return {
        n.name
        for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")
    }


def top_level_test_classes(tree: ast.Module) -> list[ast.ClassDef]:
    """Test* classes at module level that contain test_* methods."""
    out: list[ast.ClassDef] = []
    for node in tree.body:
        if not (isinstance(node, ast.ClassDef) and node.name.startswith("Test")):
            continue
        if any(
            isinstance(c, ast.FunctionDef) and c.name.startswith("test_")
            for c in node.body
        ):
            out.append(node)
    return out


def _movable_units_at_top_level(tree: ast.Module) -> list[str]:
    """All top-level names anvil would move: test_* funcs + Test* classes."""
    out: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            out.append(node.name)
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            out.append(node.name)
    return out


# ---------------------------------------------------------------------------
# Pathological-class detection
# ---------------------------------------------------------------------------


def _bad_base_reason(cls: ast.ClassDef) -> str | None:
    for b in cls.bases:
        if not (isinstance(b, ast.Name) and b.id == "object"):
            return f"inherits from non-object base ({ast.unparse(b)})"
    return None


def _has_init(cls: ast.ClassDef) -> bool:
    return any(
        isinstance(child, ast.FunctionDef) and child.name == "__init__"
        for child in cls.body
    )


def _is_self_attr(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "self"
    )


def _self_attr_reason(cls: ast.ClassDef) -> str | None:
    for child in cls.body:
        if not (isinstance(child, ast.FunctionDef) and child.name.startswith("test_")):
            continue
        for sub in ast.walk(child):
            if _is_self_attr(sub):
                return f"method {child.name} accesses self.{sub.attr}"  # type: ignore[attr-defined]
    return None


def class_is_pathological(cls: ast.ClassDef) -> str | None:
    """Return a reason if the class cannot be safely flattened, else None.

    Pathological = uses `self.<attr>` inside methods, has `__init__`,
    inherits from anything other than `object` (or empty bases).
    """
    if reason := _bad_base_reason(cls):
        return reason
    if _has_init(cls):
        return "has __init__"
    return _self_attr_reason(cls)


def _class_has_divergent_methods(cls: ast.ClassDef) -> bool:
    test_methods = [
        c
        for c in cls.body
        if isinstance(c, ast.FunctionDef) and c.name.startswith("test_")
    ]
    if len(test_methods) <= 1:
        return False
    second_tokens = {
        m.name.split("_")[1] if len(m.name.split("_")) > 1 else "" for m in test_methods
    }
    return len(second_tokens) >= 2


def file_has_pathological_class(source: Path) -> bool:
    """True iff *source* contains a Test* class that ``class_is_pathological``
    flags AND that has divergent method canonicals.

    Used by ``plan_naming`` SPLIT and ``_execute_split`` to short-circuit
    when Stage 0 was unable to flatten — avoids planning a SPLIT that
    will only partially route and leave the file mid-state.

    Cheap: only walks classes, no canonicalisation. Pathological with a
    *single* canonical is fine: the class is homogeneous and SPLIT will
    move it as a block.
    """
    try:
        tree = ast.parse(source.read_text())
    except (OSError, SyntaxError):
        return False
    return any(
        class_is_pathological(cls) is not None and _class_has_divergent_methods(cls)
        for cls in top_level_test_classes(tree)
    )


# ---------------------------------------------------------------------------
# Imports — read-side analysis (write side lives in cst_rewrite)
# ---------------------------------------------------------------------------


def _import_local_names(stmt: ast.Import | ast.ImportFrom) -> Iterator[str]:
    for alias in stmt.names:
        if isinstance(stmt, ast.Import):
            yield alias.asname or alias.name.split(".")[0]
        else:
            yield alias.asname or alias.name


def _child_stmt_blocks(stmt: ast.stmt) -> list[list[ast.stmt]]:
    if isinstance(stmt, ast.If):
        return [stmt.body, stmt.orelse]
    if isinstance(stmt, ast.Try):
        return [
            stmt.body,
            *(h.body for h in stmt.handlers),
            stmt.orelse,
            stmt.finalbody,
        ]
    return []


def collect_imported_names(
    tree: ast.Module,
) -> dict[str, tuple[ast.stmt, ast.stmt | None]]:
    """Return {imported_name: (import_stmt, enclosing_block_or_None)}.

    Walks the whole module — not just top-level — so that ``if TYPE_CHECKING``
    blocks are scanned too.  ``enclosing_block`` is the ``if TYPE_CHECKING:``
    statement (or similar) wrapping the import, or None for top-level.

    For ``from x import y`` and ``from x import y as z``, the mapping uses
    the local binding name (``y`` or ``z``).
    """
    out: dict[str, tuple[ast.stmt, ast.stmt | None]] = {}
    work: deque[tuple[list[ast.stmt], ast.stmt | None]] = deque([(tree.body, None)])
    while work:
        stmts, enclosing = work.popleft()
        for stmt in stmts:
            if isinstance(stmt, ast.Import | ast.ImportFrom):
                for local in _import_local_names(stmt):
                    out[local] = (stmt, enclosing)
                continue
            for block in _child_stmt_blocks(stmt):
                work.append((block, stmt))
    return out


def _collect_defined_names(tree: ast.Module) -> set[str]:
    """Names defined at module top-level (functions, classes, assignments)."""
    out: set[str] = set()
    for stmt in tree.body:
        if isinstance(stmt, ast.FunctionDef | ast.ClassDef | ast.AsyncFunctionDef):
            out.add(stmt.name)
        elif isinstance(stmt, ast.Assign):
            for tgt in stmt.targets:
                if isinstance(tgt, ast.Name):
                    out.add(tgt.id)
        elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            out.add(stmt.target.id)
    return out


def _iter_func_ref_nodes(
    stmt: ast.FunctionDef | ast.AsyncFunctionDef,
) -> Iterator[ast.AST]:
    yield from stmt.decorator_list
    args = stmt.args
    for arg in (*args.posonlyargs, *args.args, *args.kwonlyargs):
        if arg.annotation is not None:
            yield arg.annotation
    for special in (args.vararg, args.kwarg):
        if special is not None and special.annotation is not None:
            yield special.annotation
    for default in (*args.defaults, *args.kw_defaults):
        if default is not None:
            yield default
    if stmt.returns is not None:
        yield stmt.returns
    yield from stmt.body


def _iter_class_ref_nodes(stmt: ast.ClassDef) -> Iterator[ast.AST]:
    yield from stmt.decorator_list
    yield from stmt.bases
    for kw in stmt.keywords:
        yield kw.value
    yield from stmt.body


def _iter_stmt_ref_nodes(stmt: ast.stmt) -> Iterator[ast.AST]:
    if isinstance(stmt, ast.FunctionDef | ast.AsyncFunctionDef):
        yield from _iter_func_ref_nodes(stmt)
    elif isinstance(stmt, ast.ClassDef):
        yield from _iter_class_ref_nodes(stmt)
    elif isinstance(stmt, ast.Assign):
        yield stmt.value
    elif isinstance(stmt, ast.AnnAssign):
        if stmt.annotation is not None:
            yield stmt.annotation
        if stmt.value is not None:
            yield stmt.value
    elif isinstance(stmt, ast.If):
        yield from stmt.body
        yield from stmt.orelse


def _collect_referenced_names(tree: ast.Module) -> set[str]:
    """Names actually referenced from live top-level symbols.

    Restricted to ``Name(Load)`` reachable from:
      * decorators on top-level FunctionDef / ClassDef
      * class bases and keywords
      * argument annotations + default expressions of top-level functions
      * function bodies of top-level FunctionDef / ClassDef methods
        (excluding nested string literals, which ast.walk would otherwise
        pick up if someone embedded a textwrap.dedent block)
      * top-level Assign / AnnAssign right-hand sides

    Walking the *whole module* — as the previous implementation did —
    picks up identifiers inside dead branches, string literals parsed by
    callers via ``ast.parse(some_dedent_block)``, etc. and triggers F401
    backfills for names that aren't really used.
    """
    out: set[str] = set()
    for stmt in tree.body:
        for node in _iter_stmt_ref_nodes(stmt):
            for sub in ast.walk(node):
                if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load):
                    out.add(sub.id)
    return out


# ---------------------------------------------------------------------------
# Helpers + fixtures
# ---------------------------------------------------------------------------


def _is_pytest_fixture(node: ast.FunctionDef) -> bool:
    """True if *node* has a ``@pytest.fixture`` (or bare ``@fixture``) decorator."""
    for deco in node.decorator_list:
        target = deco.func if isinstance(deco, ast.Call) else deco
        # ``@pytest.fixture`` / ``@pytest.fixture(...)``
        if (
            isinstance(target, ast.Attribute)
            and isinstance(target.value, ast.Name)
            and target.value.id == "pytest"
            and target.attr == "fixture"
        ):
            return True
        # ``@fixture`` / ``@fixture(...)`` (when imported directly)
        if isinstance(target, ast.Name) and target.id == "fixture":
            return True
    return False


def func_body_hash(func: ast.FunctionDef) -> str:
    """Stable string hash of a function body (for collision dedup).

    Comparison is structural via ast.unparse on the body — ignores
    docstrings, comments, and minor formatting.
    """
    body = list(func.body)
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        body = body[1:]  # drop docstring
    stub = ast.Module(body=body, type_ignores=[])
    return ast.unparse(stub)


def _helper_body_hash(node: ast.FunctionDef | ast.ClassDef) -> str:
    """Hash a helper's body via ast.dump (stable, ignores comments).

    We hash body only so that two functions with identical body but
    different decorators are still treated as duplicates — decorator
    order/format is irrelevant to runtime semantics for normal helpers.
    """
    body_repr = "\n".join(ast.dump(s, annotate_fields=False) for s in node.body)
    return hashlib.sha1(body_repr.encode()).hexdigest()[:12]


def _const_value_hash(node: ast.Assign) -> str:
    """Hash a module-level constant assignment."""
    return hashlib.sha1(ast.dump(node.value).encode()).hexdigest()[:12]


def _references_file_dunder(node: ast.AST) -> bool:
    """True if *node* tree contains any reference to ``__file__``."""
    for child in ast.walk(node):
        if isinstance(child, ast.Name) and child.id == "__file__":
            return True
    return False


def _source_segment_with_decorators(text: str, node: ast.AST) -> str | None:
    """Like ``ast.get_source_segment`` but includes the decorator lines.

    ``ast.get_source_segment`` returns the segment starting at ``node.lineno``,
    which for a decorated function/class is the ``def``/``class`` line —
    decorators are lost. We extend the start back to the first decorator's
    lineno so that ``@pytest.fixture()`` is preserved when relocating a
    fixture to ``conftest.py``.
    """
    base = ast.get_source_segment(text, node)
    if base is None:
        return None
    decorators = getattr(node, "decorator_list", None)
    if not decorators:
        return base
    first_deco_line = min(d.lineno for d in decorators)
    lines = text.splitlines(keepends=True)
    prefix = "".join(lines[first_deco_line - 1 : node.lineno - 1])
    return prefix + base


def _helper_entry(node: ast.stmt) -> tuple[str, str] | None:
    """Return ``(name, body_hash)`` if *node* is a top-level helper."""
    if isinstance(node, ast.FunctionDef):
        if node.name.startswith("test_"):
            return None
        return node.name, _helper_body_hash(node)
    if isinstance(node, ast.ClassDef):
        if node.name.startswith("Test"):
            return None
        return node.name, _helper_body_hash(node)
    if isinstance(node, ast.Assign) and len(node.targets) == 1:
        tgt = node.targets[0]
        if isinstance(tgt, ast.Name) and tgt.id.isupper():
            return tgt.id, _const_value_hash(node)
    return None


def top_level_helpers(
    tree: ast.Module,
) -> dict[str, tuple[str, ast.stmt]]:
    """Return ``{name: (body_hash, node)}`` for every top-level helper.

    A helper is a top-level FunctionDef / ClassDef that is NOT a test
    (``test_*`` / ``Test*``) plus single-target uppercase ``NAME = ...``
    constants. Fixtures (``@pytest.fixture``) are included — they're
    helpers from the body-conflict perspective.
    """
    out: dict[str, tuple[str, ast.stmt]] = {}
    for node in tree.body:
        entry = _helper_entry(node)
        if entry is not None:
            name, body_hash = entry
            out[name] = (body_hash, node)
    return out


def _names_referenced_in_unit(node: ast.stmt) -> set[str]:
    """Return every ``ast.Name`` id referenced inside *node*.

    Used to determine which top-level helpers a moving unit (test_*
    function or Test* class) depends on. We also pick up marker
    arguments — ``@pytest.mark.usefixtures("X")`` is a string literal
    inside the decorator, NOT an ast.Name, so it's handled separately
    by ``marker_fixtures_in_unit``.
    """
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


# ---------------------------------------------------------------------------
# Marker fixtures (usefixtures + conftest discovery)
# ---------------------------------------------------------------------------


def _usefixtures_args(deco: ast.expr) -> list[str]:
    if not isinstance(deco, ast.Call):
        return []
    fn = deco.func
    if not (isinstance(fn, ast.Attribute) and fn.attr == "usefixtures"):
        return []
    return [
        arg.value
        for arg in deco.args
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str)
    ]


def _scannable_units(node: ast.stmt) -> list[ast.AST]:
    nodes: list[ast.AST] = [node]
    if isinstance(node, ast.ClassDef):
        nodes.extend(sub for sub in node.body if isinstance(sub, ast.FunctionDef))
    return nodes


def marker_fixtures_in_unit(node: ast.stmt) -> set[str]:
    """Return fixture names declared via ``@pytest.mark.usefixtures("X", ...)``."""
    out: set[str] = set()
    for n in _scannable_units(node):
        for deco in getattr(n, "decorator_list", []) or []:
            out.update(_usefixtures_args(deco))
    return out


def _first_string_arg(call: ast.Call) -> str | None:
    if not call.args:
        return None
    first = call.args[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        return first.value
    return None


def _getfixturevalue_literal(call: ast.Call) -> str | None:
    fn = call.func
    if not (isinstance(fn, ast.Attribute) and fn.attr == "getfixturevalue"):
        return None
    return _first_string_arg(call)


def _pytest_param_literal(call: ast.Call) -> str | None:
    fn = call.func
    if not (isinstance(fn, ast.Attribute) and fn.attr == "param"):
        return None
    if not (isinstance(fn.value, ast.Name) and fn.value.id == "pytest"):
        return None
    return _first_string_arg(call)


def _string_literal_fixtures_in_unit(node: ast.stmt) -> set[str]:
    """Return fixture names referenced via runtime string lookup.

    Two pytest idioms route a fixture through a string literal that
    static reference walks miss:

      * ``request.getfixturevalue("X")`` — dynamic fixture resolution
        inside a test body. Anvil's reference scan only sees
        ``request.getfixturevalue`` (an Attribute call) and the literal
        ``"X"`` (a Constant), so the fixture ``X`` looks unused and
        anvil leaves it in source.
      * ``pytest.param("X", ..., id=...)`` inside
        ``@pytest.mark.parametrize(("fixture_name", ...), [...])`` — the
        parametrized argument is a fixture name later resolved via
        ``request.getfixturevalue``. Same blind spot.

    This helper collects the string-literal arguments at those two
    sites so ``_collect_marker_fixtures_to_move`` can move the
    fixtures alongside their dependents. We're intentionally
    permissive: any ``request.getfixturevalue("X")`` call and any
    ``pytest.param("X", ...)`` first-arg string counts. If the string
    doesn't match a top-level fixture in source, the caller filters
    it out anyway.
    """
    out: set[str] = set()
    nodes_to_scan: list[ast.AST] = [node]
    if isinstance(node, ast.ClassDef):
        nodes_to_scan.extend(node.body)
    for n in nodes_to_scan:
        for child in ast.walk(n):
            if not isinstance(child, ast.Call):
                continue
            literal = _getfixturevalue_literal(child) or _pytest_param_literal(child)
            if literal is not None:
                out.add(literal)
    return out


def _parse_conftest_fixtures(conftest: Path) -> set[str]:
    if not conftest.exists():
        return set()
    try:
        tree = ast.parse(conftest.read_text())
    except (SyntaxError, OSError):
        return set()
    return {
        node.name
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and _is_pytest_fixture(node)
    }


def _next_ancestor(cur: Path, root: Path) -> Path | None:
    try:
        if cur.resolve() == root:
            return None
    except OSError:
        return None
    parent = cur.parent
    return None if parent == cur else parent


def _collect_conftest_fixtures(target: Path, project_path: Path) -> set[str]:
    """Return fixtures defined in any conftest on target's ancestor chain.

    Walks from target's parent up to ``project_path`` (inclusive),
    parsing every ``conftest.py`` and collecting top-level
    ``@pytest.fixture``-decorated function names. Used to short-circuit
    follow-up moves when the marker fixture is already provided.
    """
    out: set[str] = set()
    try:
        root = project_path.resolve()
    except OSError:
        return out
    cur: Path | None = target.parent
    while cur is not None:
        out |= _parse_conftest_fixtures(cur / "conftest.py")
        cur = _next_ancestor(cur, root)
    return out


def _needed_fixtures_for_moving_units(
    source_tree: ast.Module, moving_unit_names: list[str]
) -> set[str]:
    moving = set(moving_unit_names)
    needed: set[str] = set()
    for node in source_tree.body:
        if not isinstance(node, ast.FunctionDef | ast.ClassDef):
            continue
        if node.name not in moving:
            continue
        needed |= marker_fixtures_in_unit(node)
        needed |= _string_literal_fixtures_in_unit(node)
    return needed


def _source_top_level_fixtures(source_tree: ast.Module) -> set[str]:
    return {
        node.name
        for node in source_tree.body
        if isinstance(node, ast.FunctionDef) and _is_pytest_fixture(node)
    }


def _target_top_level_names(target_tree: ast.Module) -> set[str]:
    return {
        n.name
        for n in target_tree.body
        if isinstance(n, ast.FunctionDef | ast.ClassDef)
    }


def _source_top_level_definitions(
    source_tree: ast.Module,
) -> dict[str, ast.stmt]:
    """Map every top-level definition by bound name.

    Covers FunctionDef / AsyncFunctionDef / ClassDef (one name each) and
    Assign / AnnAssign with a Name target. Imports are intentionally
    excluded: anvil propagates imports separately, and we never want to
    "carry" an imported name as a source-defined statement.
    """
    defs: dict[str, ast.stmt] = {}
    for stmt in source_tree.body:
        if isinstance(stmt, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            defs[stmt.name] = stmt
        elif isinstance(stmt, ast.Assign):
            for tgt in stmt.targets:
                if isinstance(tgt, ast.Name):
                    defs[tgt.id] = stmt
        elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            defs[stmt.target.id] = stmt
    return defs


def _decorator_free_names(node: ast.FunctionDef | ast.ClassDef) -> set[str]:
    """Free ``Name(Load)`` ids referenced inside *node*'s decorators."""
    refs: set[str] = set()
    for deco in node.decorator_list:
        for sub in ast.walk(deco):
            if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load):
                refs.add(sub.id)
    return refs


def _seed_module_deps_from_units(
    source_tree: ast.Module, moving_unit_names: list[str]
) -> set[str]:
    """Initial closure seed: names directly referenced by moving units.

    Includes usefixtures markers, ``request.getfixturevalue`` / pytest.param
    string literals, AND free ``Name(Load)`` ids in decorators (which is
    how module-level constants like ``_alias = pytest.mark.skipif(...)``
    get pulled into the move).
    """
    moving = set(moving_unit_names)
    seed: set[str] = set()
    for node in source_tree.body:
        if not isinstance(node, ast.FunctionDef | ast.ClassDef):
            continue
        if node.name not in moving:
            continue
        seed |= marker_fixtures_in_unit(node)
        seed |= _string_literal_fixtures_in_unit(node)
        seed |= _decorator_free_names(node)
    return seed


def _collect_marker_fixtures_to_move(
    source_tree: ast.Module,
    target_tree: ast.Module,
    moving_unit_names: list[str],
    project_path: Path,
    target: Path,
) -> set[str]:
    """Return source-defined fixtures referenced via usefixtures markers.

    A fixture qualifies for follow-up move when:
      * It is referenced via ``@pytest.mark.usefixtures("X")`` on one
        of the moving units (or ``request.getfixturevalue`` /
        ``pytest.param`` string literal).
      * It is defined as a ``@pytest.fixture``-decorated function at
        the top level of *source*.
      * It is NOT already defined at the top level of *target* and NOT
        defined in a conftest visible to *target* (ancestor-chain).

    Decorator-referenced module-level constants (e.g. ``@_alias`` where
    ``_alias = pytest.mark.skipif(...)`` is an ``Assign`` at top of
    source) follow a separate path — see
    ``_collect_module_level_deps_to_copy``. Those are copied as text
    into the target after anvil runs, instead of being moved via
    ``move_symbols`` (which would strip them from source and break the
    anchor when the split rename happens).
    """
    needed = _needed_fixtures_for_moving_units(source_tree, moving_unit_names)
    if not needed:
        return set()
    source_fixtures = _source_top_level_fixtures(source_tree)
    target_top_names = _target_top_level_names(target_tree)
    conftest_fixtures = _collect_conftest_fixtures(target, project_path)
    return {
        name
        for name in needed
        if name in source_fixtures
        and name not in target_top_names
        and name not in conftest_fixtures
    }


def _stmt_assignment_targets(stmt: ast.stmt) -> list[str]:
    """Names bound by *stmt* if it is an Assign / AnnAssign top-level stmt."""
    if isinstance(stmt, ast.Assign):
        return [t.id for t in stmt.targets if isinstance(t, ast.Name)]
    if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
        return [stmt.target.id]
    return []


def _collect_module_level_deps_to_copy(
    source_tree: ast.Module,
    target_tree: ast.Module,
    moving_unit_names: list[str],
    project_path: Path,
    target: Path,
) -> list[str]:
    """Module-level ``Assign`` / ``AnnAssign`` deps the moving units need.

    Transitive closure (to fixed point) of names referenced inside the
    decorators of moving units, restricted to top-level ``Assign`` /
    ``AnnAssign`` definitions in *source*. The closure follows free
    ``Name(Load)`` references in the value of each carried statement,
    so ``_no_corpus = pytest.mark.skipif(not CASES, ...)`` drags
    ``_no_corpus``, then ``CASES``, recursively.

    Returns the carried names in **source order** — these constants
    will be inserted as text into the target file, and later statements
    may reference earlier ones (``B = A + 1`` after ``A = 1``).

    Excludes names already defined at the top level of *target* or in
    a visible conftest, and the moving unit names themselves (those are
    handled by anvil). Self-reference cycles are broken by a ``seen``
    guard during fixed-point iteration.
    """
    seed = _seed_module_deps_from_units(source_tree, moving_unit_names)
    if not seed:
        return []
    source_defs = _source_top_level_definitions(source_tree)
    target_top_names = _target_top_level_names(target_tree)
    conftest_fixtures = _collect_conftest_fixtures(target, project_path)
    excluded = target_top_names | conftest_fixtures | set(moving_unit_names)

    carried: set[str] = set()
    seen: set[str] = set()
    queue: list[str] = list(seed)
    while queue:
        name = queue.pop()
        if name in seen:
            continue
        seen.add(name)
        if name in excluded:
            continue
        node = source_defs.get(name)
        if not isinstance(node, ast.Assign | ast.AnnAssign):
            # Function/class defs (incl. fixtures) are NOT carried by
            # this path — anvil handles them via final_units or via
            # the usefixtures path.
            continue
        carried.add(name)
        for child in _iter_stmt_ref_nodes(node):
            for sub in ast.walk(child):
                if (
                    isinstance(sub, ast.Name)
                    and isinstance(sub.ctx, ast.Load)
                    and sub.id not in seen
                ):
                    queue.append(sub.id)
    return [
        name
        for stmt in source_tree.body
        for name in _stmt_assignment_targets(stmt)
        if name in carried
    ]
