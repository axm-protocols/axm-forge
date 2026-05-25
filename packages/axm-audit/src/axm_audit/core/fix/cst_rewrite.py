"""libcst write helpers + the import-index cache.

Everything that **mutates** Python source code lives here. Split into
five concerns:

* class flatten (``_flatten_class_to_top_level``, ``_flatten_class_child``)
* rename (``_rename_name_in_module``, ``_rename_top_level_in_source``)
* delete (``_delete_function_from_source``, ``_delete_source_if_empty_tests``)
* statement reorder (``_reorder_module_statements`` + ast helpers)
* ``Path(__file__).parents[N]`` depth patch (``_patch_file_dunder_depth``)
* import management — read-side analysis lives in ``tests_ast``; here we
  insert, dedupe, backfill, and synthesise missing imports, plus the
  project-wide import index that keeps backfill O(1) per lookup.

Hybrid I/O: we read with ``ast`` (cheap, well-tested for analysis) and
write with libcst (source-fidelity: comments, triple-quoted strings,
blank lines, quote style all preserved — what ast.unparse silently
loses).
"""

from __future__ import annotations

import ast
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import libcst as cst

from .io_primitives import _cst_load, _cst_save
from .paths import _module_path_for_test_file
from .tests_ast import (
    _BUILTINS,
    _collect_defined_names,
    _collect_imported_names,
    _collect_referenced_names,
    _walk_test_funcs,
)

__all__ = [
    # depth patch
    "_patch_file_dunder_depth",
    "_is_file_dunder_chain",
    "patch_file_depth",
    # rename / delete
    "_rename_name_in_module",
    "_rename_top_level_in_source",
    "_delete_function_from_source",
    "_delete_source_if_empty_tests",
    "rename_function",
    "delete_function",
    # class flatten
    "_flatten_class_to_top_level",
    "_flatten_class_child",
    "flatten_class",
    # statement reorder
    "_reorder_module_statements",
    "_stmt_defines",
    "_stmt_references",
    # imports — write side
    "_ast_import_to_cst",
    "_dotted_name_to_cst",
    "_is_cst_import",
    "_is_cst_type_checking_block",
    "_insert_imports_cst",
    "_dedupe_imports_cst",
    "_cst_name_to_str",
    "dedupe_imports",
    "backfill_import",
    # imports — index + backfill
    "_project_import_index",
    "_invalidate_import_index",
    "_resolve_import_for_symbol",
    "_scan_tests_for_import",
    "_synth_import_from_helpers",
    "_backfill_missing_imports",
]


# ---------------------------------------------------------------------------
# Path(__file__).parents[N] depth patch
# ---------------------------------------------------------------------------


def _patch_file_dunder_depth(
    file: Path,
    depth_delta: int,
) -> list[str]:
    """Rewrite ``Path(__file__).parents[N]`` / ``.parent.parent...`` after a move.

    When a file is relocated by *depth_delta* directory levels
    (``depth_delta = target_depth - source_depth``; negative if moved
    closer to project root, positive if moved deeper), any constant of
    the form ``Path(__file__).parents[N]`` or
    ``Path(__file__).parent.parent...`` will resolve to a different
    ancestor unless ``N`` is adjusted. We compute the new ``N`` so the
    constant continues to resolve to the *same* directory it did before
    the move:

        N_new = N_old + depth_delta

    Reasoning: a file at depth ``D`` has ``parents[N]`` at depth
    ``D - N - 1`` from project root. Moving the file to depth ``D'``
    means ``parents[N']`` is at ``D' - N' - 1``. For these to be equal,
    ``N' = N + (D' - D)`` = ``N + depth_delta``.

    Two surface forms supported (in order of preference, since some
    files mix them):

      * Subscript: ``Path(__file__).parents[N]`` (with optional
        ``.resolve()``). N is decremented by ``depth_delta``.
      * Chained: ``Path(__file__).parent.parent[.parent]*`` (with
        optional ``.resolve()``). The number of ``.parent`` accessors
        is reduced by ``depth_delta``.

    If the resulting N would be ``<= 0``, we leave the constant alone
    and emit a warning — the file was moved too close to root for the
    resolution to be expressible, indicating the relocate is suspect.
    """
    if depth_delta == 0 or not file.exists():
        return []
    module = _cst_load(file)
    if module is None:
        return []
    msgs: list[str] = []

    class _DunderPatcher(cst.CSTTransformer):
        def leave_Subscript(
            self,
            original_node: cst.Subscript,
            updated_node: cst.Subscript,
        ) -> cst.BaseExpression:
            value = updated_node.value
            if not isinstance(value, cst.Attribute):
                return updated_node
            if value.attr.value != "parents":
                return updated_node
            if not _is_file_dunder_chain(value.value):
                return updated_node
            slices = updated_node.slice
            if len(slices) != 1:
                return updated_node
            elt = slices[0].slice
            if not isinstance(elt, cst.Index):
                return updated_node
            n_node = elt.value
            if not isinstance(n_node, cst.Integer):
                return updated_node
            old_n = int(n_node.value)
            new_n = old_n + depth_delta
            if new_n <= 0:
                msgs.append(
                    f"file-depth-drift: refusing to patch {file.name} "
                    f"parents[{old_n}] (delta={depth_delta} would make "
                    f"N<=0; relocate suspicious)"
                )
                return updated_node
            msgs.append(
                f"file-depth-drift: {file.name} parents[{old_n}] -> "
                f"parents[{new_n}] (file moved by {depth_delta} level(s))"
            )
            return updated_node.with_changes(
                slice=[
                    cst.SubscriptElement(
                        slice=cst.Index(value=cst.Integer(value=str(new_n)))
                    )
                ]
            )

        def leave_Attribute(
            self,
            original_node: cst.Attribute,
            updated_node: cst.Attribute,
        ) -> cst.BaseExpression:
            if updated_node.attr.value != "parent":
                return updated_node
            count = 1
            inner: cst.BaseExpression = updated_node.value
            while isinstance(inner, cst.Attribute) and inner.attr.value == "parent":
                count += 1
                inner = inner.value
            if not _is_file_dunder_chain(inner):
                return updated_node
            return updated_node

    class _PatchChainOnce(cst.CSTTransformer):
        """Rewrite the outermost ``.parent.parent...`` chain on
        ``Path(__file__)`` exactly once.

        libcst visits ``leave_Attribute`` bottom-up. For a chain
        ``a.parent.parent.parent`` the leaves fire on the innermost
        ``a.parent`` first, then the middle, then the top. Without
        guarding, each level fires its own patch — turning
        ``.parent x3`` into ``.parent x2`` (innermost emits a refuse
        warning), then ``.parent x2 -> x1`` at middle, then again at
        top — a chain that should have been patched once gets eaten
        twice.

        Strategy: a pre-pass walks the original CST and records the
        ids of every non-top ``.parent`` link in a Path(__file__)
        chain. ``leave_Attribute`` then patches only the top nodes
        (those that are not the ``.value`` of an outer ``.parent``).
        Marker-children are returned untouched so the eventual top
        patch replaces them.
        """

        def __init__(self, suppressed_ids: set[int]) -> None:
            self._suppressed = suppressed_ids

        def leave_Attribute(
            self,
            original_node: cst.Attribute,
            updated_node: cst.Attribute,
        ) -> cst.BaseExpression:
            if id(original_node) in self._suppressed:
                return updated_node
            if updated_node.attr.value != "parent":
                return updated_node
            count = 1
            inner: cst.BaseExpression = updated_node.value
            while isinstance(inner, cst.Attribute) and inner.attr.value == "parent":
                count += 1
                inner = inner.value
            if not _is_file_dunder_chain(inner):
                return updated_node
            new_count = count + depth_delta
            if new_count <= 0:
                msgs.append(
                    f"file-depth-drift: refusing to patch {file.name} "
                    f"chain of {count} .parent (delta={depth_delta} "
                    f"would leave <=0 .parent; relocate suspicious)"
                )
                return updated_node
            rebuilt: cst.BaseExpression = inner
            for _ in range(new_count):
                rebuilt = cst.Attribute(
                    value=rebuilt,
                    attr=cst.Name(value="parent"),
                )
            msgs.append(
                f"file-depth-drift: {file.name} "
                f".parent x{count} -> .parent x{new_count} "
                f"(file moved by {depth_delta} level(s))"
            )
            return rebuilt

    class _CollectChainChildren(cst.CSTVisitor):
        """Pre-pass: ids of every ``.parent`` Attribute that is the
        ``.value`` of another ``.parent`` Attribute (= not the top of
        its chain). The transformer skips those — only top nodes get
        patched.
        """

        def __init__(self) -> None:
            self.child_ids: set[int] = set()

        def visit_Attribute(self, node: cst.Attribute) -> None:
            if node.attr.value != "parent":
                return
            if (
                isinstance(node.value, cst.Attribute)
                and node.value.attr.value == "parent"
            ):
                self.child_ids.add(id(node.value))

    new_module = module.visit(_DunderPatcher())
    assert isinstance(new_module, cst.Module)
    # Collect ids AFTER _DunderPatcher: libcst rebuilds nodes during
    # a visit even when no transformation is returned, so ids captured
    # on `module` would not match the nodes inside `new_module`.
    collector = _CollectChainChildren()
    new_module.visit(collector)
    new_module = new_module.visit(_PatchChainOnce(collector.child_ids))
    assert isinstance(new_module, cst.Module)
    if new_module.code != module.code:
        _cst_save(file, new_module)
    return msgs


def _is_file_dunder_chain(expr: cst.BaseExpression) -> bool:
    """True if *expr* is a syntactic ``Path(__file__)`` or
    ``Path(__file__).resolve()`` (possibly nested via ``Path(__file__)``)."""
    if (
        isinstance(expr, cst.Call)
        and isinstance(expr.func, cst.Attribute)
        and expr.func.attr.value == "resolve"
        and not expr.args
    ):
        expr = expr.func.value
    if not isinstance(expr, cst.Call):
        return False
    if not isinstance(expr.func, cst.Name) or expr.func.value != "Path":
        return False
    if len(expr.args) != 1:
        return False
    arg = expr.args[0].value
    return isinstance(arg, cst.Name) and arg.value == "__file__"


# ---------------------------------------------------------------------------
# Class flatten
# ---------------------------------------------------------------------------


def _flatten_class_to_top_level(source_text: str, class_name: str) -> str:
    """Transform `class TestX: def test_a(self, ...): ...` into top-level funcs.

    Removes the class wrapper; promotes each test_* method by dropping
    `self` from its parameter list. Decorators, comments and blank lines
    around each method are preserved (libcst is lossless on these).
    Other bodies inside the class (helpers, fixtures) are also promoted
    to top-level — they may conflict with module-level names; caller is
    expected to verify with _class_is_pathological first.

    Class-level decorators that apply to every method (``@pytest.mark.*``
    including ``usefixtures``) are propagated onto each promoted test
    function so behaviour is preserved across the flatten. Decorators
    that don't make sense at function level (anything that isn't a
    ``pytest.mark.*`` or bare ``mark.*``) are dropped with the class.
    """
    module = cst.parse_module(source_text)
    new_body: list[cst.BaseStatement] = []
    for stmt in module.body:
        if not (isinstance(stmt, cst.ClassDef) and stmt.name.value == class_name):
            new_body.append(stmt)
            continue
        class_decos = tuple(d for d in stmt.decorators if _is_pytest_mark_decorator(d))
        for child in stmt.body.body:
            promoted = _flatten_class_child(child, class_decos)
            if promoted is not None:
                new_body.append(promoted)
    return module.with_changes(body=new_body).code


def _is_pytest_mark_decorator(deco: cst.Decorator) -> bool:
    """True iff *deco* is ``@pytest.mark.X`` or ``@pytest.mark.X(...)``.

    Class-level pytest marks (``integration``, ``e2e``, ``usefixtures``,
    custom markers) apply to every method, so they must follow the
    methods when the class is flattened. Other class decorators
    (``@dataclass``, ``@pytest.fixture``, custom adapters) don't have
    that semantics — they are dropped with the class wrapper.
    """
    node = deco.decorator
    if isinstance(node, cst.Call):
        node = node.func
    if not isinstance(node, cst.Attribute):
        return False
    parent = node.value
    if not (isinstance(parent, cst.Attribute) and parent.attr.value == "mark"):
        return False
    grand = parent.value
    return isinstance(grand, cst.Name) and grand.value == "pytest"


def _flatten_class_child(
    child: cst.BaseStatement,
    class_decorators: tuple[cst.Decorator, ...] = (),
) -> cst.BaseStatement | None:
    """Promote one child of a Test* class body to module level.

    Returns None to drop (class docstring); returns the (possibly
    rewritten) statement otherwise. For FunctionDef, strips the ``self``
    parameter so the promoted top-level function takes the same args
    pytest expects, and prepends ``class_decorators`` (class-level
    pytest marks) so behaviour-affecting markers survive the flatten.
    Helpers and fixtures inside the class don't receive class-level
    marks — they aren't tests and pytest marks have no effect on them.
    """
    if isinstance(child, cst.SimpleStatementLine) and len(child.body) == 1:
        inner = child.body[0]
        if isinstance(inner, cst.Expr) and isinstance(
            inner.value, cst.SimpleString | cst.ConcatenatedString
        ):
            return None
    if isinstance(child, cst.FunctionDef):
        params = child.params
        new_params = params
        if params.params and params.params[0].name.value == "self":
            new_params = params.with_changes(params=tuple(params.params[1:]))
        new_decorators = class_decorators + tuple(child.decorators)
        return child.with_changes(params=new_params, decorators=new_decorators)
    return child


# ---------------------------------------------------------------------------
# Rename / delete
# ---------------------------------------------------------------------------


def _rename_name_in_module(path: Path, old_to_new: dict[str, str]) -> None:
    """Rename every occurrence of name X across module *path* (def + refs).

    Renames at three sites simultaneously:
      * the ``cst.FunctionDef`` / ``cst.ClassDef`` definition itself,
      * every ``cst.Name`` reference in the module body,
      * marker-argument string literals like
        ``@pytest.mark.usefixtures("X")`` so usefixtures still resolves
        after the rename.

    Preserves formatting via libcst. Unlike
    ``_rename_top_level_in_source`` (which only renames the def header
    — needed for cross-file move collisions), this rewrites references
    too — needed when source helpers get renamed to avoid colliding with
    target's same-named helpers.
    """
    if not old_to_new:
        return
    module = _cst_load(path)
    if module is None:
        return

    class _Renamer(cst.CSTTransformer):
        def __init__(self, mapping: dict[str, str]) -> None:
            self.mapping = mapping

        def leave_Name(
            self, original_node: cst.Name, updated_node: cst.Name
        ) -> cst.BaseExpression:
            if updated_node.value in self.mapping:
                return updated_node.with_changes(value=self.mapping[updated_node.value])
            return updated_node

        def leave_FunctionDef(
            self,
            original_node: cst.FunctionDef,
            updated_node: cst.FunctionDef,
        ) -> cst.BaseStatement:
            if updated_node.name.value in self.mapping:
                return updated_node.with_changes(
                    name=cst.Name(value=self.mapping[updated_node.name.value])
                )
            return updated_node

        def leave_ClassDef(
            self,
            original_node: cst.ClassDef,
            updated_node: cst.ClassDef,
        ) -> cst.BaseStatement:
            if updated_node.name.value in self.mapping:
                return updated_node.with_changes(
                    name=cst.Name(value=self.mapping[updated_node.name.value])
                )
            return updated_node

        def leave_SimpleString(
            self,
            original_node: cst.SimpleString,
            updated_node: cst.SimpleString,
        ) -> cst.BaseExpression:
            raw = updated_node.value
            if len(raw) < 2:
                return updated_node
            quote = raw[0]
            if quote not in {'"', "'"}:
                return updated_node
            inner = raw[1:-1]
            if inner in self.mapping:
                return updated_node.with_changes(
                    value=f"{quote}{self.mapping[inner]}{quote}"
                )
            return updated_node

    new_module = module.visit(_Renamer(old_to_new))
    assert isinstance(new_module, cst.Module)
    _cst_save(path, new_module)


def _rename_top_level_in_source(source: Path, old_to_new: dict[str, str]) -> None:
    """Rename top-level FunctionDef / ClassDef in *source*, preserving formatting.

    Workaround for axm-anvil's ``rename=`` parameter, which validates
    target absence under the ORIGINAL name before applying the rename —
    so it cannot resolve cross-file collisions on its own. By renaming in
    source first, we hand anvil a clean conflict-free move.
    """
    if not old_to_new:
        return
    module = _cst_load(source)
    if module is None:
        return
    new_body = []
    for stmt in module.body:
        if (
            isinstance(stmt, cst.FunctionDef | cst.ClassDef)
            and stmt.name.value in old_to_new
        ):
            stmt = stmt.with_changes(name=cst.Name(value=old_to_new[stmt.name.value]))
        new_body.append(stmt)
    _cst_save(source, module.with_changes(body=new_body))


def _delete_function_from_source(source: Path, func_name: str) -> None:
    """Remove a top-level FunctionDef from source, preserving formatting."""
    module = _cst_load(source)
    if module is None:
        return
    new_body = [
        stmt
        for stmt in module.body
        if not (isinstance(stmt, cst.FunctionDef) and stmt.name.value == func_name)
    ]
    _cst_save(source, module.with_changes(body=new_body))


def _delete_source_if_empty_tests(source: Path) -> None:
    """git rm the source if no test_* funcs/classes remain."""
    if not source.exists():
        return
    tree = ast.parse(source.read_text())
    if _walk_test_funcs(tree):
        return
    rc = subprocess.run(
        ["git", "rm", "-q", str(source)],
        capture_output=True,
        text=True,
    )
    if rc.returncode != 0:
        source.unlink()


# ---------------------------------------------------------------------------
# Statement reorder
# ---------------------------------------------------------------------------


def _stmt_defines(stmt: ast.stmt) -> set[str]:
    """Names a top-level statement defines (for the module-level scope)."""
    out: set[str] = set()
    if isinstance(stmt, ast.FunctionDef | ast.ClassDef | ast.AsyncFunctionDef):
        out.add(stmt.name)
    elif isinstance(stmt, ast.Assign):
        for tgt in stmt.targets:
            if isinstance(tgt, ast.Name):
                out.add(tgt.id)
    elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
        out.add(stmt.target.id)
    elif isinstance(stmt, ast.Import):
        for alias in stmt.names:
            out.add(alias.asname or alias.name.split(".")[0])
    elif isinstance(stmt, ast.ImportFrom):
        for alias in stmt.names:
            out.add(alias.asname or alias.name)
    return out


def _names_in(node: ast.AST) -> set[str]:
    return {sub.id for sub in ast.walk(node) if isinstance(sub, ast.Name)}


def _stmt_reference_roots(stmt: ast.stmt) -> list[ast.AST]:
    if isinstance(stmt, ast.FunctionDef | ast.AsyncFunctionDef):
        return list(stmt.decorator_list)
    if isinstance(stmt, ast.ClassDef):
        return [
            *stmt.decorator_list,
            *stmt.bases,
            *(kw.value for kw in stmt.keywords),
        ]
    if isinstance(stmt, ast.Assign | ast.Expr):
        return [stmt.value]
    if isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
        return [stmt.value]
    return []


def _stmt_references(stmt: ast.stmt) -> set[str]:
    """Names a statement references at MODULE-EXECUTION time.

    For a FunctionDef/ClassDef, this is the *decorators* and class bases,
    NOT the body (the body executes when the function is called, not at
    module import). For an Assign, this is the right-hand side.
    """
    out: set[str] = set()
    for root in _stmt_reference_roots(stmt):
        out |= _names_in(root)
    return out


def _load_cst_ast_pair(
    path: Path,
) -> tuple[cst.Module, list[ast.stmt]] | None:
    # Parse with both libcst (write side) and ast (analysis side); bail if
    # they disagree on top-level count.
    cst_module = _cst_load(path)
    if cst_module is None:
        return None
    try:
        ast_tree = ast.parse(cst_module.code)
    except SyntaxError:
        return None
    if len(cst_module.body) != len(ast_tree.body):
        return None
    return cst_module, ast_tree.body


def _build_reordered_body(
    body_cst: list,
    head_idx: list[int],
    rest_idx: list[int],
    earliest: list[int],
    docstring_idx: int | None,
) -> list:
    order = sorted(range(len(rest_idx)), key=lambda p: (earliest[p], p))
    new_rest_idx = [rest_idx[p] for p in order]
    new_body: list = []
    if docstring_idx is not None:
        new_body.append(body_cst[docstring_idx])
    new_body.extend(body_cst[i] for i in head_idx)
    new_body.extend(body_cst[i] for i in new_rest_idx)
    return new_body


def _find_docstring_idx(body_ast: list[ast.stmt]) -> int | None:
    # PEP 257: docstring must be the very first non-import statement.
    for i, stmt in enumerate(body_ast):
        if (
            isinstance(stmt, ast.Expr)
            and isinstance(stmt.value, ast.Constant)
            and isinstance(stmt.value.value, str)
        ):
            return i
        if isinstance(stmt, ast.Import | ast.ImportFrom):
            continue
        return None
    return None


def _partition_head_rest(
    body_ast: list[ast.stmt], docstring_idx: int | None
) -> tuple[list[int], list[int]]:
    # Imports up to first non-import become head; stray imports after are folded in.
    head_idx: list[int] = []
    rest_idx: list[int] = []
    stray_imports: list[int] = []
    seen_non_head = False
    for i, stmt in enumerate(body_ast):
        if i == docstring_idx:
            continue
        is_import = isinstance(stmt, ast.Import | ast.ImportFrom)
        if not seen_non_head and is_import:
            head_idx.append(i)
        elif is_import:
            stray_imports.append(i)
        else:
            seen_non_head = True
            rest_idx.append(i)
    return head_idx + stray_imports, rest_idx


def _compute_earliest(
    body_ast: list[ast.stmt], head_idx: list[int], rest_idx: list[int]
) -> tuple[list[int], bool]:
    head_names: set[str] = set()
    for i in head_idx:
        head_names |= _stmt_defines(body_ast[i])
    name_to_pos: dict[str, int] = {}
    for pos, i in enumerate(rest_idx):
        for n in _stmt_defines(body_ast[i]):
            name_to_pos[n] = pos
    earliest: list[int] = [0] * len(rest_idx)
    needs_change = False
    for pos, i in enumerate(rest_idx):
        refs = _stmt_references(body_ast[i]) - head_names
        min_pos = max(
            (name_to_pos[ref] + 1 for ref in refs if ref in name_to_pos),
            default=0,
        )
        earliest[pos] = min_pos
        if min_pos > pos:
            needs_change = True
    return earliest, needs_change


def _reorder_module_statements(path: Path) -> None:
    """Reorder a module's top-level statements so definitions precede uses.

    After SPLIT/MERGE/FLATTEN, axm-anvil can leave statements in an order
    that breaks Python's module-execution semantics:
      * ``_skip_no_tools = pytest.mark.skipif(_tools_available())`` before
        ``def _tools_available()`` → NameError at import.
      * ``@_skip_no_tools`` decorator on a class, before the assign that
        defines ``_skip_no_tools`` → NameError.

    Strategy: stable topological sort. Imports stay first (they have no
    intra-module deps). For the rest, each statement is placed after the
    last statement that defines a name it references at module-execution
    time. References inside function bodies do NOT count — they're
    deferred. Order is preserved within independent groups.

    Implementation note: we parse twice — once with libcst (the source
    of truth for formatting; what we'll write back) and once with ast
    (for cheap defines/references analysis). The libcst statements are
    reordered by index, not rebuilt, so triple-quoted strings, comments,
    and blank-line spacing all survive intact.

    Idempotent.
    """
    loaded = _load_cst_ast_pair(path)
    if loaded is None:
        return
    cst_module, body_ast = loaded
    body_cst = list(cst_module.body)

    docstring_idx = _find_docstring_idx(body_ast)
    head_idx, rest_idx = _partition_head_rest(body_ast, docstring_idx)
    earliest, needs_change = _compute_earliest(body_ast, head_idx, rest_idx)

    docstring_misplaced = docstring_idx is not None and docstring_idx != 0
    if not needs_change and not docstring_misplaced:
        return

    new_body_cst = _build_reordered_body(
        body_cst, head_idx, rest_idx, earliest, docstring_idx
    )
    new_text = cst_module.with_changes(body=new_body_cst).code
    if new_text != cst_module.code:
        path.write_text(new_text)


# ---------------------------------------------------------------------------
# Imports — write side + index + backfill
# ---------------------------------------------------------------------------


def _ast_import_to_cst(stmt: ast.stmt) -> cst.SimpleStatementLine:
    """Convert an ast import statement to a libcst SimpleStatementLine.

    Handles ``import x``, ``import x as y``, ``import x.y``, ``from m
    import a, b as c``, and relative ``from .m import x`` forms. Any
    other ast node is wrapped as a trailing comment line — should not
    happen in practice since the buckets only contain ast.Import /
    ast.ImportFrom from ``_collect_imported_names``.
    """
    if isinstance(stmt, ast.Import):
        names = [
            cst.ImportAlias(
                name=_dotted_name_to_cst(a.name),
                asname=cst.AsName(name=cst.Name(a.asname)) if a.asname else None,
            )
            for a in stmt.names
        ]
        return cst.SimpleStatementLine(body=[cst.Import(names=names)])
    if isinstance(stmt, ast.ImportFrom):
        names = [
            cst.ImportAlias(
                name=cst.Name(a.name),
                asname=cst.AsName(name=cst.Name(a.asname)) if a.asname else None,
            )
            for a in stmt.names
        ]
        module = _dotted_name_to_cst(stmt.module) if stmt.module else None
        return cst.SimpleStatementLine(
            body=[
                cst.ImportFrom(
                    module=module,
                    names=names,
                    relative=[cst.Dot()] * (stmt.level or 0),
                )
            ]
        )
    return cst.SimpleStatementLine(
        body=[cst.Expr(cst.SimpleString(value='"# unrecognised import"'))]
    )


def _dotted_name_to_cst(dotted: str) -> cst.Attribute | cst.Name:
    """Build a libcst dotted name from ``a.b.c``."""
    parts = dotted.split(".")
    node: cst.Attribute | cst.Name = cst.Name(parts[0])
    for part in parts[1:]:
        node = cst.Attribute(value=node, attr=cst.Name(part))
    return node


def _is_cst_import(stmt: cst.BaseStatement) -> bool:
    """True iff stmt is a SimpleStatementLine wrapping Import/ImportFrom."""
    if not isinstance(stmt, cst.SimpleStatementLine):
        return False
    return any(isinstance(small, cst.Import | cst.ImportFrom) for small in stmt.body)


def _is_cst_type_checking_block(stmt: cst.BaseStatement) -> bool:
    """True iff stmt is ``if TYPE_CHECKING:`` (no elif, no else conditions matter)."""
    if not isinstance(stmt, cst.If):
        return False
    test = stmt.test
    return isinstance(test, cst.Name) and test.value == "TYPE_CHECKING"


def _insert_imports_cst(
    module: cst.Module,
    top_level: list[cst.SimpleStatementLine],
    type_checking: list[cst.SimpleStatementLine],
) -> list[cst.BaseStatement]:
    """Return a new top-level body with the new imports placed sensibly.

    Top-level imports go after the last existing top-level import (or at
    the start). TYPE_CHECKING-bucket imports go into an existing
    ``if TYPE_CHECKING:`` block if present, else into a new one
    (preceded by ``from typing import TYPE_CHECKING`` if needed).
    """
    body = list(module.body)

    last_import_idx = -1
    for i, stmt in enumerate(body):
        if _is_cst_import(stmt):
            last_import_idx = i
    insert_at = last_import_idx + 1
    if top_level:
        body = body[:insert_at] + list(top_level) + body[insert_at:]

    if not type_checking:
        return body

    for i, stmt in enumerate(body):
        if _is_cst_type_checking_block(stmt):
            assert isinstance(stmt, cst.If)
            new_inner = list(stmt.body.body) + list(type_checking)
            body[i] = stmt.with_changes(body=stmt.body.with_changes(body=new_inner))
            return body

    has_tc_import = False
    for stmt in body:
        if not isinstance(stmt, cst.SimpleStatementLine):
            continue
        for small in stmt.body:
            if isinstance(small, cst.ImportFrom):
                mod = small.module
                if (
                    isinstance(mod, cst.Name)
                    and mod.value == "typing"
                    and any(
                        isinstance(a.name, cst.Name) and a.name.value == "TYPE_CHECKING"
                        for a in small.names
                    )
                ):
                    has_tc_import = True

    new_block = cst.If(
        test=cst.Name("TYPE_CHECKING"),
        body=cst.IndentedBlock(body=list(type_checking)),
    )
    insert_pos = last_import_idx + 1 + len(top_level)
    if has_tc_import:
        body = body[:insert_pos] + [new_block] + body[insert_pos:]
    else:
        tc_import = cst.SimpleStatementLine(
            body=[
                cst.ImportFrom(
                    module=cst.Name("typing"),
                    names=[cst.ImportAlias(name=cst.Name("TYPE_CHECKING"))],
                    relative=[],
                )
            ]
        )
        body = body[:insert_pos] + [tc_import, new_block] + body[insert_pos:]
    return body


@dataclass(slots=True)
class _DedupeState:
    triples: set[tuple[str, str, str | None]] = field(default_factory=set)
    locals_: set[str] = field(default_factory=set)

    def key_of(
        self, prefix: str, alias: cst.ImportAlias
    ) -> tuple[str, str, str | None]:
        name = _cst_name_to_str(alias.name)
        asname = (
            _cst_name_to_str(alias.asname.name) if alias.asname is not None else None
        )
        return (prefix, name, asname)

    def local_name(self, prefix: str, alias: cst.ImportAlias) -> str:
        if alias.asname is not None:
            return _cst_name_to_str(alias.asname.name)
        full = _cst_name_to_str(alias.name)
        if prefix == "":
            return full.split(".")[0]
        return full

    def is_duplicate(self, prefix: str, alias: cst.ImportAlias) -> bool:
        return (
            self.key_of(prefix, alias) in self.triples
            or self.local_name(prefix, alias) in self.locals_
        )

    def record(self, prefix: str, alias: cst.ImportAlias) -> None:
        self.triples.add(self.key_of(prefix, alias))
        self.locals_.add(self.local_name(prefix, alias))

    def keep_aliases(
        self, prefix: str, aliases: Sequence[cst.ImportAlias]
    ) -> list[cst.ImportAlias]:
        kept = [a for a in aliases if not self.is_duplicate(prefix, a)]
        for a in kept:
            self.record(prefix, a)
        return kept


def _import_from_prefix(small: cst.ImportFrom) -> str:
    level = len(small.relative)
    module_str = _cst_name_to_str(small.module) if small.module else ""
    return "." * level + module_str


def _dedupe_small(
    small: cst.BaseSmallStatement, state: _DedupeState
) -> cst.BaseSmallStatement | None:
    if isinstance(small, cst.Import):
        kept = state.keep_aliases("", small.names)
        return small.with_changes(names=kept) if kept else None
    if isinstance(small, cst.ImportFrom):
        if isinstance(small.names, cst.ImportStar):
            return small
        kept = state.keep_aliases(_import_from_prefix(small), small.names)
        return small.with_changes(names=kept) if kept else None
    return small


def _dedupe_simple_line(
    stmt: cst.SimpleStatementLine, state: _DedupeState
) -> cst.SimpleStatementLine | None:
    new_small: list[cst.BaseSmallStatement] = []
    for small in stmt.body:
        replaced = _dedupe_small(small, state)
        if replaced is not None:
            new_small.append(replaced)
    if not new_small:
        return None
    return stmt.with_changes(body=new_small)


def _dedupe_block(
    stmts: Sequence[cst.BaseStatement], state: _DedupeState
) -> list[cst.BaseStatement]:
    out: list[cst.BaseStatement] = []
    for stmt in stmts:
        if isinstance(stmt, cst.SimpleStatementLine):
            replaced = _dedupe_simple_line(stmt, state)
            if replaced is not None:
                out.append(replaced)
            continue
        out.append(stmt)
    return out


def _dedupe_tc_block(stmt: cst.If, state: _DedupeState) -> cst.If | None:
    new_inner = _dedupe_block(stmt.body.body, state)
    if not new_inner:
        return None
    return stmt.with_changes(body=stmt.body.with_changes(body=new_inner))


def _dedupe_imports_cst(module: cst.Module) -> cst.Module:
    """Collapse duplicate import bindings at module top-level and in TC blocks.

    Two-level dedup:
      1. Exact-triple ``(module, name, asname)`` — the obvious case where
         the same merge re-injects an identical import.
      2. **Local-binding shadow** — when a later alias would shadow an
         earlier *local name* even though it comes from a different
         module (e.g. ``from a import X`` then ``from a.b import X``).
         Ruff's F811 catches this; we drop the later one (first import
         wins, matching Python's normal "first binding survives until
         re-bound" execution semantics — which is what authors usually
         expected when both happened to land in the same file via merges).
    """
    state = _DedupeState()
    new_body: list[cst.BaseStatement] = []
    for stmt in module.body:
        if isinstance(stmt, cst.SimpleStatementLine):
            replaced = _dedupe_simple_line(stmt, state)
            if replaced is not None:
                new_body.append(replaced)
            continue
        if _is_cst_type_checking_block(stmt):
            assert isinstance(stmt, cst.If)
            replaced_tc = _dedupe_tc_block(stmt, state)
            if replaced_tc is not None:
                new_body.append(replaced_tc)
            continue
        new_body.append(stmt)
    return module.with_changes(body=new_body)


def _cst_name_to_str(
    node: cst.BaseExpression | cst.Name | cst.Attribute,
) -> str:
    """Stringify a (possibly dotted) cst Name/Attribute."""
    if isinstance(node, cst.Name):
        return node.value
    if isinstance(node, cst.Attribute):
        return f"{_cst_name_to_str(node.value)}.{node.attr.value}"
    return ""


# ---------------------------------------------------------------------------
# Project-wide import index (mutable cache + invalidation)
# ---------------------------------------------------------------------------


_PROJECT_IMPORT_INDEX_CACHE: dict[
    Path, dict[str, tuple[ast.stmt, ast.stmt | None]]
] = {}


def _project_import_index(
    project_path: Path,
) -> dict[str, tuple[ast.stmt, ast.stmt | None]]:
    """Build (and cache) ``{name: (import_stmt, enclosing_block)}`` for the project.

    Walks every ``test_*.py`` under ``tests/`` ONCE and indexes every
    imported name. Subsequent calls reuse the cache — without it,
    ``_scan_tests_for_import`` re-parses ~170 files per missing name and
    dominates wall time (7 min+ on the corpus).
    """
    if project_path in _PROJECT_IMPORT_INDEX_CACHE:
        return _PROJECT_IMPORT_INDEX_CACHE[project_path]
    index: dict[str, tuple[ast.stmt, ast.stmt | None]] = {}
    seen_dirs: set[Path] = set()
    for tdir in ("tests/integration", "tests/e2e", "tests/unit", "tests"):
        d = project_path / tdir
        if not d.exists() or d in seen_dirs:
            continue
        seen_dirs.add(d)
        for p in d.rglob("test_*.py"):
            try:
                tree = ast.parse(p.read_text())
            except (SyntaxError, OSError):
                continue
            for name, pair in _collect_imported_names(tree).items():
                index.setdefault(name, pair)
    _PROJECT_IMPORT_INDEX_CACHE[project_path] = index
    return index


def _invalidate_import_index(project_path: Path) -> None:
    """Drop the cached import index for *project_path*."""
    _PROJECT_IMPORT_INDEX_CACHE.pop(project_path, None)


def _build_project_symbol_index(
    project_path: Path,
) -> dict[str, tuple[ast.stmt, ast.stmt | None]]:
    """Scan every ``.py`` file under *project_path* for top-level names.

    Returns ``{name: (ast.ImportFrom, None)}`` where the ImportFrom is a
    freshly parsed statement ready to be transplanted. Skips common
    vendor / build / cache directories so we do not crawl ``.venv`` or
    ``node_modules`` on every cache rebuild.
    """
    index: dict[str, tuple[ast.stmt, ast.stmt | None]] = {}
    skip_parts = {
        ".venv",
        "venv",
        "__pycache__",
        ".git",
        "build",
        "dist",
        "node_modules",
        ".tox",
        ".mypy_cache",
        ".ruff_cache",
        ".pytest_cache",
    }
    for p in project_path.rglob("*.py"):
        if any(part in skip_parts for part in p.parts):
            continue
        try:
            rel = p.relative_to(project_path)
        except ValueError:
            continue
        parts = list(rel.with_suffix("").parts)
        if parts and parts[-1] == "__init__":
            parts = parts[:-1]
        if not parts:
            continue
        module_path = ".".join(parts)
        try:
            tree = ast.parse(p.read_text())
        except (SyntaxError, OSError, UnicodeDecodeError):
            continue
        for node in tree.body:
            if not isinstance(
                node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef
            ):
                continue
            name = node.name
            if name in index:
                continue
            try:
                stmt = ast.parse(f"from {module_path} import {name}").body[0]
            except SyntaxError:
                continue
            index[name] = (stmt, None)
    return index


def _resolve_import_for_symbol(
    project_path: Path, symbol: str
) -> tuple[ast.stmt, ast.stmt | None] | None:
    """Return the import statement that brings *symbol* into scope, or ``None``.

    Builds (and caches in ``_PROJECT_IMPORT_INDEX_CACHE``) a project-wide
    index of top-level FunctionDef / AsyncFunctionDef / ClassDef
    definitions across every ``.py`` file under *project_path*. Drop the
    cache via :func:`_invalidate_import_index` after mutating the file
    tree so the next call rebuilds.
    """
    if project_path not in _PROJECT_IMPORT_INDEX_CACHE:
        _PROJECT_IMPORT_INDEX_CACHE[project_path] = _build_project_symbol_index(
            project_path
        )
    return _PROJECT_IMPORT_INDEX_CACHE[project_path].get(symbol)


# ---------------------------------------------------------------------------
# Public in-memory rewriters (cst.Module → cst.Module)
# ---------------------------------------------------------------------------


def flatten_class(module: cst.Module, class_name: str) -> cst.Module:
    """Flatten the *class_name* class into top-level functions.

    In-memory variant of :func:`_flatten_class_to_top_level`. Class-level
    pytest marks are propagated onto each promoted method; method-level
    decorators are preserved verbatim; the class docstring is dropped.
    """
    new_body: list[cst.BaseStatement] = []
    for stmt in module.body:
        if not (isinstance(stmt, cst.ClassDef) and stmt.name.value == class_name):
            new_body.append(stmt)
            continue
        class_decos = tuple(d for d in stmt.decorators if _is_pytest_mark_decorator(d))
        for child in stmt.body.body:
            promoted = _flatten_class_child(child, class_decos)
            if promoted is not None:
                new_body.append(promoted)
    return module.with_changes(body=new_body)


def rename_function(module: cst.Module, old_name: str, new_name: str) -> cst.Module:
    """Rename top-level function *old_name* to *new_name* across *module*.

    Updates the ``FunctionDef`` itself, any ``Name`` reference, and any
    string-literal argument (e.g. ``pytest.mark.parametrize("old", …)``)
    that matches *old_name*. In-memory counterpart of
    :func:`_rename_name_in_module`.
    """
    mapping = {old_name: new_name}

    class _Renamer(cst.CSTTransformer):
        def leave_Name(
            self, original_node: cst.Name, updated_node: cst.Name
        ) -> cst.BaseExpression:
            if updated_node.value in mapping:
                return updated_node.with_changes(value=mapping[updated_node.value])
            return updated_node

        def leave_FunctionDef(
            self,
            original_node: cst.FunctionDef,
            updated_node: cst.FunctionDef,
        ) -> cst.BaseStatement:
            if updated_node.name.value in mapping:
                return updated_node.with_changes(
                    name=cst.Name(value=mapping[updated_node.name.value])
                )
            return updated_node

        def leave_SimpleString(
            self,
            original_node: cst.SimpleString,
            updated_node: cst.SimpleString,
        ) -> cst.BaseExpression:
            raw = updated_node.value
            if len(raw) < 2 or raw[0] not in {'"', "'"}:
                return updated_node
            inner = raw[1:-1]
            if inner in mapping:
                return updated_node.with_changes(
                    value=f"{raw[0]}{mapping[inner]}{raw[0]}"
                )
            return updated_node

    result = module.visit(_Renamer())
    assert isinstance(result, cst.Module)
    return result


def delete_function(module: cst.Module, func_name: str) -> cst.Module:
    """Drop top-level function *func_name* from *module*.

    Neighbouring statements (and their attached blank-line spacing) are
    preserved by libcst's leading-lines semantics. In-memory counterpart
    of :func:`_delete_function_from_source`.
    """
    new_body = [
        stmt
        for stmt in module.body
        if not (isinstance(stmt, cst.FunctionDef) and stmt.name.value == func_name)
    ]
    return module.with_changes(body=new_body)


def patch_file_depth(module: cst.Module, depth_delta: int = 0) -> cst.Module:
    """Rewrite ``Path(__file__).parents[N]`` literals by *depth_delta*.

    In-memory variant of :func:`_patch_file_dunder_depth` that targets the
    subscript form only — the chained ``.parent.parent`` form is left for
    the file-level helper. Identity transform when *depth_delta* is 0 or
    the pattern is absent.
    """
    if depth_delta == 0:
        return module

    class _DunderPatcher(cst.CSTTransformer):
        def leave_Subscript(
            self,
            original_node: cst.Subscript,
            updated_node: cst.Subscript,
        ) -> cst.BaseExpression:
            value = updated_node.value
            if not isinstance(value, cst.Attribute):
                return updated_node
            if value.attr.value != "parents":
                return updated_node
            if not _is_file_dunder_chain(value.value):
                return updated_node
            slices = updated_node.slice
            if len(slices) != 1:
                return updated_node
            elt = slices[0].slice
            if not isinstance(elt, cst.Index):
                return updated_node
            n_node = elt.value
            if not isinstance(n_node, cst.Integer):
                return updated_node
            new_n = int(n_node.value) + depth_delta
            if new_n <= 0:
                return updated_node
            return updated_node.with_changes(
                slice=[
                    cst.SubscriptElement(
                        slice=cst.Index(value=cst.Integer(value=str(new_n)))
                    )
                ]
            )

    result = module.visit(_DunderPatcher())
    assert isinstance(result, cst.Module)
    return result


def dedupe_imports(module: cst.Module) -> cst.Module:
    """Public wrapper around :func:`_dedupe_imports_cst`."""
    return _dedupe_imports_cst(module)


def _collect_alias_names(
    aliases: Sequence[cst.ImportAlias], *, strip_dot: bool
) -> set[str]:
    out: set[str] = set()
    for a in aliases:
        if a.asname is not None:
            out.add(_cst_name_to_str(a.asname.name))
            continue
        raw = _cst_name_to_str(a.name)
        out.add(raw.split(".")[0] if strip_dot else raw)
    return out


def _existing_import_names(module: cst.Module) -> set[str]:
    existing: set[str] = set()
    for stmt in module.body:
        if not isinstance(stmt, cst.SimpleStatementLine):
            continue
        for small in stmt.body:
            if isinstance(small, cst.Import):
                existing |= _collect_alias_names(small.names, strip_dot=True)
            elif isinstance(small, cst.ImportFrom) and not isinstance(
                small.names, cst.ImportStar
            ):
                existing |= _collect_alias_names(small.names, strip_dot=False)
    return existing


def _build_import_lines(
    mapping: dict[str, str], existing: set[str]
) -> list[cst.SimpleStatementLine]:
    lines: list[cst.SimpleStatementLine] = []
    for name, mod_path in mapping.items():
        if name in existing:
            continue
        lines.append(
            cst.SimpleStatementLine(
                body=[
                    cst.ImportFrom(
                        module=_dotted_name_to_cst(mod_path),
                        names=[cst.ImportAlias(name=cst.Name(name))],
                        relative=[],
                    )
                ]
            )
        )
    return lines


def _future_import_insert_index(body: Sequence[cst.BaseStatement]) -> int:
    insert_at = 0
    for i, stmt in enumerate(body):
        if not isinstance(stmt, cst.SimpleStatementLine):
            continue
        for small in stmt.body:
            if not isinstance(small, cst.ImportFrom):
                continue
            mod = small.module
            if isinstance(mod, cst.Name) and mod.value == "__future__":
                insert_at = i + 1
                break
    return insert_at


def backfill_import(module: cst.Module, mapping: dict[str, str]) -> cst.Module:
    """Insert ``from {mod} import {name}`` for each (name → mod) in *mapping*.

    The new imports go at the canonical position — after every
    ``from __future__ import …`` (or at the module top when none exists)
    and before the first non-import statement. Names already imported in
    *module* are skipped, so this is idempotent on already-correct sources.
    """
    if not mapping:
        return module

    new_imports = _build_import_lines(mapping, _existing_import_names(module))
    if not new_imports:
        return module

    body = list(module.body)
    insert_at = _future_import_insert_index(body)
    return module.with_changes(body=body[:insert_at] + new_imports + body[insert_at:])


def _scan_tests_for_import(
    project_path: Path, name: str
) -> tuple[ast.stmt, ast.stmt | None] | None:
    """O(1) lookup of an imported *name* anywhere in the project's tests."""
    return _project_import_index(project_path).get(name)


def _synth_import_from_helpers(
    name: str, project_path: Path, target: Path
) -> tuple[ast.stmt, ast.stmt | None] | None:
    """Synthesize ``from tests.<tier>._helpers import <name>`` if defined there.

    Scans every ``tests/<tier>/_helpers.py`` for a top-level ``def name``
    or ``class name`` or ``NAME = ...`` and returns a freshly-parsed
    ``ast.ImportFrom`` node ready to be transplanted by
    ``_backfill_missing_imports``. The second tuple element (enclosing
    block) is always ``None`` — these synthesized imports are top-level.
    """
    tests_root = project_path / "tests"
    if not tests_root.is_dir():
        return None
    for tier in ("integration", "e2e", "unit"):
        helpers = tests_root / tier / "_helpers.py"
        if not helpers.is_file():
            continue
        try:
            tree = ast.parse(helpers.read_text())
        except (SyntaxError, OSError):
            continue
        for node in tree.body:
            defined = (
                isinstance(node, ast.FunctionDef | ast.ClassDef) and node.name == name
            ) or (
                isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == name
            )
            if not defined:
                continue
            module = _module_path_for_test_file(helpers, project_path)
            if module is None:
                return None
            stmt = ast.parse(f"from {module} import {name}").body[0]
            return (stmt, None)
    return None


def _backfill_missing_imports(
    source: Path, target: Path, project_path: Path | None = None
) -> list[str]:
    """Copy imports from *source* into *target* for names target uses but doesn't define.

    Falls back to scanning all test files under ``project_path`` if the
    immediate source doesn't have the import — covers cases where the
    original import was lost by an earlier move.

    Hybrid: analyse with ast (cheap, well-tested), write with libcst so
    triple-quoted strings, blank lines, and comments in the target file
    are preserved byte-for-byte.
    """
    if not target.exists():
        return []
    try:
        tgt_tree = ast.parse(target.read_text())
    except SyntaxError:
        return []
    src_tree: ast.Module | None = None
    if source.exists():
        try:
            src_tree = ast.parse(source.read_text())
        except SyntaxError:
            src_tree = None

    src_imports = _collect_imported_names(src_tree) if src_tree else {}
    tgt_imports = _collect_imported_names(tgt_tree)
    tgt_defined = _collect_defined_names(tgt_tree)
    tgt_refs = _collect_referenced_names(tgt_tree)

    missing = (
        tgt_refs
        - set(tgt_imports.keys())
        - tgt_defined
        - _BUILTINS
        - {"self", "cls", "True", "False", "None"}
    )
    recoverable: dict[str, tuple[ast.stmt, ast.stmt | None]] = {
        name: src_imports[name] for name in missing if name in src_imports
    }
    still_missing = missing - set(recoverable.keys())
    if still_missing and project_path is not None:
        for name in still_missing:
            found = _scan_tests_for_import(project_path, name)
            if found is not None:
                recoverable[name] = found
        still_missing2 = missing - set(recoverable.keys())
        if still_missing2 and project_path is not None:
            for name in still_missing2:
                synth = _synth_import_from_helpers(name, project_path, target)
                if synth is not None:
                    recoverable[name] = synth

    if not recoverable:
        return []

    top_level_ast: list[ast.stmt] = []
    type_checking_ast: list[ast.stmt] = []
    seen_top: set[int] = set()
    seen_tc: set[int] = set()
    msgs: list[str] = []
    for name, (stmt, enclosing) in recoverable.items():
        msgs.append(f"backfilled import for `{name}` from {source.name}")
        is_tc = (
            enclosing is not None
            and isinstance(enclosing, ast.If)
            and isinstance(enclosing.test, ast.Name)
            and enclosing.test.id == "TYPE_CHECKING"
        )
        bucket, seen = (
            (type_checking_ast, seen_tc) if is_tc else (top_level_ast, seen_top)
        )
        if id(stmt) not in seen:
            bucket.append(stmt)
            seen.add(id(stmt))

    top_level_cst = [_ast_import_to_cst(s) for s in top_level_ast]
    type_checking_cst = [_ast_import_to_cst(s) for s in type_checking_ast]

    cst_module = _cst_load(target)
    if cst_module is None:
        return msgs
    new_body = _insert_imports_cst(cst_module, top_level_cst, type_checking_cst)
    new_module = cst_module.with_changes(body=new_body)
    new_module = _dedupe_imports_cst(new_module)
    _cst_save(target, new_module)
    return msgs
