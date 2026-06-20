"""TypeScript / JavaScript language backend (tree-sitter-typescript).

Maps the TypeScript grammar's concrete syntax tree into the shared, language-
agnostic symbol model so every downstream ``ast_*`` tool works on ``.ts``/``.tsx``
exactly as on ``.py``. The grammar package (``tree-sitter-typescript``) is an
optional dependency imported lazily here — a Python-only install never loads it,
and the registry skips this backend if the import fails.

Node-name mapping (the part that differs from Python):

* ``function_declaration`` / arrow funcs in ``lexical_declaration`` → function
* ``class_declaration`` → class (kind=class)
* ``interface_declaration`` → class-like (kind=interface)
* ``type_alias_declaration`` → class-like (kind=type)
* ``enum_declaration`` → class-like (kind=enum)
* ``import_statement`` → ES6 import (relative if the source starts with ``.``)
* ``export_statement`` wraps any of the above → unwrapped, marked exported.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from tree_sitter import Language, Parser, Tree

from axm_ast.models.nodes import (
    ClassInfo,
    ClassKind,
    FunctionInfo,
    ImportInfo,
    ModuleInfo,
)

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from tree_sitter import Node

__all__ = ["TypeScriptBackend"]

_thread_local = threading.local()


def _build_language() -> Language:
    """Build the tree-sitter TypeScript ``Language`` (lazy, optional dep).

    Raises:
        ImportError: If ``tree-sitter-typescript`` is not installed — the
            registry catches this and leaves ``.ts`` unsupported.
    """
    import tree_sitter_typescript as tstypescript

    return Language(tstypescript.language_typescript())


def _get_parser() -> Parser:
    """Return this thread's lazily-built TypeScript parser (non-reentrant)."""
    parser: Parser | None = getattr(_thread_local, "ts_parser", None)
    if parser is None:
        parser = Parser(_build_language())
        _thread_local.ts_parser = parser
    return parser


def _text(node: Node | None) -> str:
    """Return a node's source text, or empty string for a missing node."""
    if node is None or node.text is None:
        return ""
    return node.text.decode("utf-8", errors="replace")


def _name_of(node: Node) -> str | None:
    """Return the ``name`` child's text for a declaration node."""
    name_node = node.child_by_field_name("name")
    return _text(name_node) if name_node is not None else None


def _line_span(node: Node) -> tuple[int, int]:
    """Return the 1-indexed (start, end) line span of *node*."""
    return (node.start_point[0] + 1, node.end_point[0] + 1)


def _walk(node: Node) -> Iterator[Node]:
    """Yield *node* and all its descendants (pre-order)."""
    yield node
    for child in node.children:
        yield from _walk(child)


class TypeScriptBackend:
    """TypeScript/JS backend implementing the ``LanguageBackend`` interface."""

    @property
    def name(self) -> str:
        """Language name."""
        return "typescript"

    @property
    def suffixes(self) -> tuple[str, ...]:
        """TypeScript and TSX source extensions."""
        return (".ts", ".tsx")

    def parse_source(self, source: str) -> Tree:
        """Parse TypeScript *source* into a tree-sitter ``Tree``."""
        parser = _get_parser()
        return parser.parse(source.encode("utf-8"))

    def parse_file(self, path: Path) -> Tree:
        """Parse a ``.ts``/``.tsx`` file into a tree-sitter ``Tree``."""
        from pathlib import Path as _Path

        resolved = _Path(path).resolve()
        if not resolved.exists():
            msg = f"File not found: {resolved}"
            raise FileNotFoundError(msg)
        source = resolved.read_text(encoding="utf-8", errors="replace")
        return self.parse_source(source)

    def extract_module(self, path: Path) -> ModuleInfo:
        """Extract symbols from a TypeScript file into a :class:`ModuleInfo`."""
        from pathlib import Path as _Path

        resolved = _Path(path).resolve()
        tree = self.parse_file(resolved)
        functions: list[FunctionInfo] = []
        classes: list[ClassInfo] = []
        imports: list[ImportInfo] = []

        for child in tree.root_node.children:
            # An `export` statement wraps the real declaration; unwrap it.
            node = self._unwrap_export(child)
            self._dispatch(node, functions, classes, imports)

        return ModuleInfo(
            path=resolved,
            functions=functions,
            classes=classes,
            imports=imports,
        )

    @staticmethod
    def _unwrap_export(node: Node) -> Node:
        """Return the declaration inside an ``export`` statement, else *node*."""
        if node.type != "export_statement":
            return node
        decl = node.child_by_field_name("declaration")
        return decl if decl is not None else node

    # Class-like declarations map node-type → ClassKind in one table.
    _CLASS_KINDS: dict[str, ClassKind] = {  # noqa: RUF012
        "class_declaration": ClassKind.CLASS,
        "interface_declaration": ClassKind.INTERFACE,
        "type_alias_declaration": ClassKind.TYPE_ALIAS,
        "enum_declaration": ClassKind.ENUM,
    }

    def _dispatch(
        self,
        node: Node,
        functions: list[FunctionInfo],
        classes: list[ClassInfo],
        imports: list[ImportInfo],
    ) -> None:
        """Route a top-level node to the right symbol collector."""
        kind = self._CLASS_KINDS.get(node.type)
        if kind is not None:
            classes.append(self._class_like(node, kind))
            return
        if node.type == "function_declaration":
            fn = self._function(node)
        elif node.type == "lexical_declaration":
            fn = self._arrow_function(node)
        else:
            if node.type == "import_statement":
                imp = self._import(node)
                if imp is not None:
                    imports.append(imp)
            return
        if fn is not None:
            functions.append(fn)

    def _function(self, node: Node, *, is_async: bool = False) -> FunctionInfo | None:
        """Build a FunctionInfo from a ``function_declaration`` node."""
        name = _name_of(node)
        if name is None:
            return None
        start, end = _line_span(node)
        ret = node.child_by_field_name("return_type")
        async_kw = is_async or any(c.type == "async" for c in node.children)
        return FunctionInfo(
            name=name,
            return_type=_text(ret).lstrip(": ") or None if ret is not None else None,
            line_start=start,
            line_end=end,
            is_async=async_kw,
        )

    def _arrow_function(self, node: Node) -> FunctionInfo | None:
        """Build a FunctionInfo from a ``const f = () => …`` declaration."""
        declarator = next(
            (c for c in node.children if c.type == "variable_declarator"), None
        )
        if declarator is None:
            return None
        value = declarator.child_by_field_name("value")
        if value is None or value.type not in ("arrow_function", "function_expression"):
            return None
        name = _text(declarator.child_by_field_name("name"))
        if not name:
            return None
        start, end = _line_span(node)
        is_async = any(c.type == "async" for c in value.children)
        return FunctionInfo(
            name=name, line_start=start, line_end=end, is_async=is_async
        )

    def _class_like(self, node: Node, kind: ClassKind) -> ClassInfo:
        """Build a ClassInfo for a class/interface/type/enum declaration."""
        name = _name_of(node) or "<anonymous>"
        start, end = _line_span(node)
        return ClassInfo(name=name, kind=kind, line_start=start, line_end=end)

    def _import(self, node: Node) -> ImportInfo | None:
        """Build an ImportInfo from an ES6 ``import`` statement."""
        source = next((c for c in node.children if c.type == "string"), None)
        module = _text(source).strip("\"'") if source is not None else None
        is_relative = bool(module and module.startswith("."))
        names = [
            _text(spec.child_by_field_name("name") or spec)
            for spec in _walk(node)
            if spec.type == "import_specifier"
        ]
        return ImportInfo(module=module, names=names, is_relative=is_relative)
