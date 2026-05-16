"""Read-only AST inspection: tests, classes, imports, helpers, markers.

All helpers operate on ``ast.Module`` / ``ast.stmt`` nodes from the stdlib
``ast`` module — no libcst, no mutation, no I/O beyond ``Path.read_text``
when an entry point takes a path. This file gathers every read-side AST
primitive used by the fix pipeline so that ``cst_rewrite`` / ``stages_*``
can stay focused on side-effects.

Future: the higher-level pieces (``_top_level_test_classes``,
``_top_level_helpers``, ``_collect_imported_names``) may move to
``axm-ast`` once that package exposes raw ``ast.Module`` access. The
fine-grained walkers (``_class_is_pathological``, ``_marker_fixtures_in_unit``)
are too specific to pytest semantics to belong in a general lib.
"""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path

__all__ = [
    "_BUILTINS",
    "_walk_test_funcs",
    "_top_level_test_names",
    "_top_level_test_classes",
    "_movable_units_at_top_level",
    "_class_is_pathological",
    "_file_has_pathological_class",
    "_collect_imported_names",
    "_collect_defined_names",
    "_collect_referenced_names",
    "_top_level_helpers",
    "_names_referenced_in_unit",
    "_is_pytest_fixture",
    "_func_body_hash",
    "_helper_body_hash",
    "_const_value_hash",
    "_references_file_dunder",
    "_source_segment_with_decorators",
    "_marker_fixtures_in_unit",
    "_collect_marker_fixtures_to_move",
    "_collect_conftest_fixtures",
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


def _top_level_test_classes(tree: ast.Module) -> list[ast.ClassDef]:
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


def _class_is_pathological(cls: ast.ClassDef) -> str | None:
    """Return a reason if the class cannot be safely flattened, else None.

    Pathological = uses `self.<attr>` inside methods, has `__init__`,
    inherits from anything other than `object` (or empty bases).
    """
    if cls.bases:
        for b in cls.bases:
            if not (isinstance(b, ast.Name) and b.id == "object"):
                return f"inherits from non-object base ({ast.unparse(b)})"
    for child in cls.body:
        if isinstance(child, ast.FunctionDef) and child.name == "__init__":
            return "has __init__"
    # Detect `self.<attr>` reads/writes — these would break a flatten
    for child in cls.body:
        if not (
            isinstance(child, ast.FunctionDef) and child.name.startswith("test_")
        ):
            continue
        for sub in ast.walk(child):
            if (
                isinstance(sub, ast.Attribute)
                and isinstance(sub.value, ast.Name)
                and sub.value.id == "self"
            ):
                return f"method {child.name} accesses self.{sub.attr}"
    return None


def _file_has_pathological_class(source: Path) -> bool:
    """True iff *source* contains a Test* class that ``_class_is_pathological``
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
    for cls in _top_level_test_classes(tree):
        if _class_is_pathological(cls) is None:
            continue
        # Count distinct test method names that would land in different
        # canonical buckets — cheap proxy without full canonicalisation:
        # if all method names share a common prefix the class is likely
        # homogeneous; otherwise divergent.
        test_methods = [
            c for c in cls.body
            if isinstance(c, ast.FunctionDef) and c.name.startswith("test_")
        ]
        if len(test_methods) <= 1:
            continue
        # Cheap heuristic: distinct second-token across methods is a
        # strong proxy for divergent canonical filenames (e.g.
        # test_patch_ci_* vs test_patch_publish_* land in different
        # buckets). Avoids invoking the full canonical machinery here.
        second_tokens = {
            m.name.split("_")[1] if len(m.name.split("_")) > 1 else ""
            for m in test_methods
        }
        if len(second_tokens) >= 2:
            return True
    return False


# ---------------------------------------------------------------------------
# Imports — read-side analysis (write side lives in cst_rewrite)
# ---------------------------------------------------------------------------


def _collect_imported_names(
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

    def visit(stmts: list[ast.stmt], enclosing: ast.stmt | None) -> None:
        for stmt in stmts:
            if isinstance(stmt, ast.Import):
                for alias in stmt.names:
                    local = alias.asname or alias.name.split(".")[0]
                    out[local] = (stmt, enclosing)
            elif isinstance(stmt, ast.ImportFrom):
                for alias in stmt.names:
                    local = alias.asname or alias.name
                    out[local] = (stmt, enclosing)
            elif isinstance(stmt, ast.If):
                # if TYPE_CHECKING: ... — walk into both branches with self
                # as the enclosing wrapper
                visit(stmt.body, stmt)
                visit(stmt.orelse, stmt)
            elif isinstance(stmt, ast.Try):
                visit(stmt.body, stmt)
                for handler in stmt.handlers:
                    visit(handler.body, stmt)
                visit(stmt.orelse, stmt)
                visit(stmt.finalbody, stmt)

    visit(tree.body, None)
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

    def add_names(node: ast.AST) -> None:
        for sub in ast.walk(node):
            if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load):
                out.add(sub.id)

    for stmt in tree.body:
        if isinstance(stmt, ast.FunctionDef | ast.AsyncFunctionDef):
            for dec in stmt.decorator_list:
                add_names(dec)
            for arg in (
                *stmt.args.posonlyargs,
                *stmt.args.args,
                *stmt.args.kwonlyargs,
            ):
                if arg.annotation is not None:
                    add_names(arg.annotation)
            if stmt.args.vararg and stmt.args.vararg.annotation:
                add_names(stmt.args.vararg.annotation)
            if stmt.args.kwarg and stmt.args.kwarg.annotation:
                add_names(stmt.args.kwarg.annotation)
            for default in (*stmt.args.defaults, *stmt.args.kw_defaults):
                if default is not None:
                    add_names(default)
            if stmt.returns is not None:
                add_names(stmt.returns)
            for child in stmt.body:
                add_names(child)
        elif isinstance(stmt, ast.ClassDef):
            for dec in stmt.decorator_list:
                add_names(dec)
            for base in stmt.bases:
                add_names(base)
            for kw in stmt.keywords:
                add_names(kw.value)
            for child in stmt.body:
                add_names(child)
        elif isinstance(stmt, ast.Assign):
            add_names(stmt.value)
        elif isinstance(stmt, ast.AnnAssign):
            if stmt.annotation is not None:
                add_names(stmt.annotation)
            if stmt.value is not None:
                add_names(stmt.value)
        elif isinstance(stmt, ast.If):
            # if TYPE_CHECKING: imports live here, not interesting; but
            # other guarded code (e.g. version checks) may reference real
            # symbols. Walk the bodies but not the test (which uses names
            # like TYPE_CHECKING that we don't want to flag).
            for child in (*stmt.body, *stmt.orelse):
                add_names(child)
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


def _func_body_hash(func: ast.FunctionDef) -> str:
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


def _top_level_helpers(
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
        if isinstance(node, ast.FunctionDef):
            if node.name.startswith("test_"):
                continue
            out[node.name] = (_helper_body_hash(node), node)
        elif isinstance(node, ast.ClassDef):
            if node.name.startswith("Test"):
                continue
            out[node.name] = (_helper_body_hash(node), node)
        elif isinstance(node, ast.Assign) and len(node.targets) == 1:
            tgt = node.targets[0]
            if isinstance(tgt, ast.Name) and tgt.id.isupper():
                out[tgt.id] = (_const_value_hash(node), node)
    return out


def _names_referenced_in_unit(node: ast.stmt) -> set[str]:
    """Return every ``ast.Name`` id referenced inside *node*.

    Used to determine which top-level helpers a moving unit (test_*
    function or Test* class) depends on. We also pick up marker
    arguments — ``@pytest.mark.usefixtures("X")`` is a string literal
    inside the decorator, NOT an ast.Name, so it's handled separately
    by ``_marker_fixtures_in_unit``.
    """
    return {
        n.id for n in ast.walk(node)
        if isinstance(n, ast.Name)
    }


# ---------------------------------------------------------------------------
# Marker fixtures (usefixtures + conftest discovery)
# ---------------------------------------------------------------------------


def _marker_fixtures_in_unit(node: ast.stmt) -> set[str]:
    """Return fixture names declared via ``@pytest.mark.usefixtures("X", ...)``.

    Scans the unit's decorator list (and its methods' decorator lists if
    it's a class) for ``pytest.mark.usefixtures`` calls and collects
    every string-literal argument. Other markers (``pytest.mark.parametrize``,
    ``pytest.mark.skipif``, ...) are ignored.
    """
    out: set[str] = set()
    nodes_to_scan: list[ast.AST] = [node]
    if isinstance(node, ast.ClassDef):
        nodes_to_scan.extend(
            sub for sub in node.body
            if isinstance(sub, ast.FunctionDef)
        )
    for n in nodes_to_scan:
        decorators = getattr(n, "decorator_list", []) or []
        for deco in decorators:
            if not isinstance(deco, ast.Call):
                continue
            # Match ``<...>.usefixtures(...)``
            fn = deco.func
            if not (isinstance(fn, ast.Attribute) and fn.attr == "usefixtures"):
                continue
            for arg in deco.args:
                if (
                    isinstance(arg, ast.Constant)
                    and isinstance(arg.value, str)
                ):
                    out.add(arg.value)
    return out


def _collect_conftest_fixtures(target: Path, project_path: Path) -> set[str]:
    """Return fixtures defined in any conftest on target's ancestor chain.

    Walks from target's parent up to ``project_path`` (inclusive),
    parsing every ``conftest.py`` and collecting top-level
    ``@pytest.fixture``-decorated function names. Used to short-circuit
    follow-up moves when the marker fixture is already provided.
    """
    out: set[str] = set()
    cur = target.parent
    try:
        root = project_path.resolve()
    except OSError:
        return out
    while True:
        conftest = cur / "conftest.py"
        if conftest.exists():
            try:
                tree = ast.parse(conftest.read_text())
            except (SyntaxError, OSError):
                pass
            else:
                for node in tree.body:
                    if (
                        isinstance(node, ast.FunctionDef)
                        and _is_pytest_fixture(node)
                    ):
                        out.add(node.name)
        try:
            if cur.resolve() == root:
                break
        except OSError:
            break
        parent = cur.parent
        if parent == cur:
            break
        cur = parent
    return out


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
        of the moving units.
      * It is defined as a ``@pytest.fixture``-decorated function at
        the top level of *source*.
      * It is NOT already defined at the top level of *target* and NOT
        defined in a conftest visible to *target* (ancestor-chain).
    """
    moving = set(moving_unit_names)
    needed: set[str] = set()
    for node in source_tree.body:
        if isinstance(node, ast.FunctionDef | ast.ClassDef) and node.name in moving:
            needed |= _marker_fixtures_in_unit(node)
    if not needed:
        return set()
    source_fixtures: dict[str, ast.FunctionDef] = {}
    for node in source_tree.body:
        if isinstance(node, ast.FunctionDef) and _is_pytest_fixture(node):
            source_fixtures[node.name] = node
    target_top_names = {
        n.name
        for n in target_tree.body
        if isinstance(n, ast.FunctionDef | ast.ClassDef)
    }
    conftest_fixtures = _collect_conftest_fixtures(target, project_path)
    return {
        name for name in needed
        if name in source_fixtures
        and name not in target_top_names
        and name not in conftest_fixtures
    }
