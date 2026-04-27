"""Tree-sitter based Python source parser.

This module provides deterministic, fast parsing of Python source files
using tree-sitter. It extracts structured information (functions, classes,
imports, variables, docstrings) from the concrete syntax tree.

Example:
    >>> from pathlib import Path
    >>> from axm_ast.core.parser import extract_module_info
    >>> mod = extract_module_info(Path("my_module.py"))
    >>> [f.name for f in mod.functions]
    `['main', 'helper']`
"""

from __future__ import annotations

import logging
from pathlib import Path

import tree_sitter_python as tspython
from tree_sitter import Language, Node, Parser, Tree

from axm_ast.models.nodes import (
    ClassInfo,
    FunctionInfo,
    FunctionKind,
    ImportInfo,
    ModuleInfo,
    ParameterInfo,
    VariableInfo,
)

logger = logging.getLogger(__name__)

__all__ = [
    "extract_module_info",
    "parse_file",
    "parse_source",
]

_MAX_VALUE_REPR_LEN = 80

_TRIVIA_NODE_TYPES = frozenset({"comment", "newline"})
_DOCSTRING_NODE_TYPES = frozenset({"string", "concatenated_string"})

# ─── Language & Parser singleton ─────────────────────────────────────────────

PY_LANGUAGE = Language(tspython.language())

_parser: Parser | None = None


def _get_parser() -> Parser:
    """Return a lazily-initialized tree-sitter parser."""
    global _parser
    if _parser is None:
        _parser = Parser(PY_LANGUAGE)
    return _parser


# ─── Low-level parsing ──────────────────────────────────────────────────────


def parse_source(source: str) -> Tree:
    """Parse a Python source string into a tree-sitter Tree.

    Args:
        source: Python source code as string.

    Returns:
        Parsed tree-sitter Tree.

    Example:
        >>> tree = parse_source("def foo(): pass")
        >>> tree.root_node.type
        'module'
    """
    parser = _get_parser()
    return parser.parse(source.encode("utf-8"))


def parse_file(path: Path) -> Tree:
    """Parse a Python file into a tree-sitter Tree.

    Args:
        path: Path to a .py file.

    Returns:
        Parsed tree-sitter Tree.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file is not a .py file.

    Example:
        >>> from pathlib import Path
        >>> tree = parse_file(Path("setup.py"))
        >>> tree.root_node.type
        'module'
    """
    path = Path(path).resolve()
    if not path.exists():
        msg = f"File not found: {path}"
        raise FileNotFoundError(msg)
    if path.suffix != ".py":
        msg = f"Not a Python file: {path}"
        raise ValueError(msg)
    source = path.read_text(encoding="utf-8")
    return parse_source(source)


# ─── Node text helper ────────────────────────────────────────────────────────


def _node_text(node: Node | None) -> str | None:
    """Extract UTF-8 text from a tree-sitter node."""
    if node is None:
        return None
    raw_text = node.text
    if isinstance(raw_text, bytes):
        return raw_text.decode("utf-8")
    return str(raw_text)


def _unquote(text: str) -> str:
    """Remove surrounding quotes from a string literal."""
    for prefix in ('"""', "'''", '"', "'"):
        if text.startswith(prefix) and text.endswith(prefix):
            return text[len(prefix) : -len(prefix)]
    return text


# ─── Extraction helpers ──────────────────────────────────────────────────────


def _body_children(node: Node) -> list[Node]:
    """Return body children of a function/class, or direct children for a module."""
    body = node.child_by_field_name("body")
    return list(body.children if body is not None else node.children)


def _first_non_trivia_child(children: list[Node]) -> Node | None:
    """Return the first child that is not a comment or newline."""
    return next((c for c in children if c.type not in _TRIVIA_NODE_TYPES), None)


def _string_value(stmt: Node) -> str | None:
    """Return the unquoted string of an expression-statement string, else None."""
    if stmt.type != "expression_statement":
        return None
    expr = stmt.children[0] if stmt.children else None
    if expr is None or expr.type not in _DOCSTRING_NODE_TYPES:
        return None
    raw = _node_text(expr)
    return _unquote(raw) if raw else None


def _extract_docstring(node: Node) -> str | None:
    """Return the docstring of a function/class/module node, or None.

    Looks at the first non-trivia statement in the body and returns its
    unquoted string when it is a bare string expression.
    """
    first = _first_non_trivia_child(_body_children(node))
    return _string_value(first) if first is not None else None


def _extract_decorators(node: Node) -> list[str]:
    """Extract decorator names from a decorated definition."""
    decorators: list[str] = []
    for child in node.children:
        if child.type == "decorator":
            # Get the expression after @
            parts = [
                _node_text(c)
                for c in child.children
                if c.type not in ("@", "comment", "newline")
            ]
            dec_text = "".join(p for p in parts if p)
            if dec_text:
                decorators.append(dec_text)
    return decorators


def _classify_function(decorators: list[str], parent_type: str) -> FunctionKind:
    """Determine function kind from decorators and context."""
    dec_names = {d.split("(")[0].split(".")[-1] for d in decorators}

    if "abstractmethod" in dec_names:
        return FunctionKind.ABSTRACT
    if "property" in dec_names:
        return FunctionKind.PROPERTY
    if "classmethod" in dec_names:
        return FunctionKind.CLASSMETHOD
    if "staticmethod" in dec_names:
        return FunctionKind.STATICMETHOD
    if parent_type == "class_definition":
        return FunctionKind.METHOD
    return FunctionKind.FUNCTION


def _extract_parameters(node: Node) -> list[ParameterInfo]:
    """Extract parameter list from a function definition node."""
    params_node = node.child_by_field_name("parameters")
    if params_node is None:
        return []

    params: list[ParameterInfo] = []
    for child in params_node.children:
        if child.type in ("(", ")", ",", "comment"):
            continue
        param = _extract_single_param(child)
        if param is not None:
            params.append(param)
    return params


def _extract_single_param(node: Node) -> ParameterInfo | None:
    """Extract a single parameter from various node types."""
    handlers = {
        "identifier": _param_from_identifier,
        "typed_parameter": _param_from_typed,
        "default_parameter": _param_from_default,
        "typed_default_parameter": _param_from_typed_default,
        "list_splat_pattern": _param_from_splat,
        "dictionary_splat_pattern": _param_from_splat,
    }
    handler = handlers.get(node.type)
    return handler(node) if handler else None


def _param_from_identifier(node: Node) -> ParameterInfo:
    return ParameterInfo(name=_node_text(node) or "")


def _param_from_typed(node: Node) -> ParameterInfo:
    name_node = node.children[0] if node.children else None
    type_node = node.child_by_field_name("type")
    return ParameterInfo(
        name=_node_text(name_node) or "",
        annotation=_node_text(type_node),
    )


def _param_from_default(node: Node) -> ParameterInfo:
    name_node = node.child_by_field_name("name")
    value_node = node.child_by_field_name("value")
    return ParameterInfo(
        name=_node_text(name_node) or "",
        default=_node_text(value_node),
    )


def _param_from_typed_default(node: Node) -> ParameterInfo:
    name_node = node.child_by_field_name("name")
    type_node = node.child_by_field_name("type")
    value_node = node.child_by_field_name("value")
    return ParameterInfo(
        name=_node_text(name_node) or "",
        annotation=_node_text(type_node),
        default=_node_text(value_node),
    )


def _param_from_splat(node: Node) -> ParameterInfo:
    name_node = node.children[1] if len(node.children) > 1 else None
    prefix = "**" if node.type == "dictionary_splat_pattern" else "*"
    return ParameterInfo(name=prefix + (_node_text(name_node) or ""))


def _extract_return_type(node: Node) -> str | None:
    """Extract return type annotation from function definition."""
    ret_node = node.child_by_field_name("return_type")
    return _node_text(ret_node)


def _extract_function(node: Node, parent_type: str = "module") -> FunctionInfo:
    """Extract a FunctionInfo from a function_definition node."""
    name_node = node.child_by_field_name("name")
    name = _node_text(name_node) or "<anonymous>"
    decorators = _extract_decorators(node)
    params = _extract_parameters(node)
    return_type = _extract_return_type(node)
    docstring = _extract_docstring(node)
    kind = _classify_function(decorators, parent_type)
    is_async = node.type == "function_definition" and any(
        _node_text(c) == "async" for c in node.children
    )

    return FunctionInfo(
        name=name,
        params=params,
        return_type=return_type,
        docstring=docstring,
        decorators=decorators,
        kind=kind,
        line_start=node.start_point.row + 1,
        line_end=node.end_point.row + 1,
        is_async=is_async,
    )


def _extract_class(node: Node) -> ClassInfo:
    """Extract a ClassInfo from a class_definition node."""
    name_node = node.child_by_field_name("name")
    name = _node_text(name_node) or "<anonymous>"
    decorators = _extract_decorators(node)
    docstring = _extract_docstring(node)
    bases = _extract_bases(node)
    methods = _extract_methods(node)

    return ClassInfo(
        name=name,
        bases=bases,
        methods=methods,
        docstring=docstring,
        decorators=decorators,
        line_start=node.start_point.row + 1,
        line_end=node.end_point.row + 1,
    )


def _extract_bases(node: Node) -> list[str]:
    """Extract base classes from a class_definition node."""
    bases: list[str] = []
    superclasses = node.child_by_field_name("superclasses")
    if superclasses is not None:
        for child in superclasses.children:
            if child.type not in ("(", ")", ",", "comment"):
                base_text = _node_text(child)
                if base_text:
                    bases.append(base_text)
    return bases


def _extract_methods(node: Node) -> list[FunctionInfo]:
    """Extract methods from a class body."""
    methods: list[FunctionInfo] = []
    body = node.child_by_field_name("body")
    if body is None:
        return methods

    for child in body.children:
        if child.type == "function_definition":
            methods.append(_extract_function(child, parent_type="class_definition"))
        elif child.type == "decorated_definition":
            _extract_decorated_method(child, methods)
    return methods


def _extract_decorated_method(node: Node, methods: list[FunctionInfo]) -> None:
    """Extract a decorated method and apply its decorators."""
    func_node = node
    for sub in node.children:
        if sub.type == "function_definition":
            func_node = sub
            break
    func = _extract_function(func_node, parent_type="class_definition")
    decs = _extract_decorators(node)
    func = func.model_copy(
        update={
            "decorators": decs,
            "kind": _classify_function(decs, "class_definition"),
        }
    )
    methods.append(func)


def _extract_imports(node: Node) -> list[ImportInfo]:
    """Extract import information from an import node."""
    if node.type == "import_statement":
        return _extract_import_statement(node)
    if node.type in ("import_from_statement", "future_import_statement"):
        return _extract_from_imports(node)
    return []


def _extract_import_statement(node: Node) -> list[ImportInfo]:
    """Extract imports from a plain `import x` statement."""
    imports: list[ImportInfo] = []
    for child in node.children:
        if child.type == "dotted_name":
            module_name = _node_text(child)
            imports.append(ImportInfo(module=module_name, names=[module_name or ""]))
        elif child.type == "aliased_import":
            name_node = child.child_by_field_name("name")
            alias_node = child.child_by_field_name("alias")
            module_name = _node_text(name_node)
            alias = _node_text(alias_node)
            imports.append(
                ImportInfo(
                    module=module_name,
                    names=[module_name or ""],
                    alias=alias,
                )
            )
    return imports


def _extract_from_imports(node: Node) -> list[ImportInfo]:
    """Extract imports from a `from x import y` statement."""
    module_name, level = _extract_from_module(node)
    is_relative = level > 0
    names: list[str] = []
    from_alias: str | None = None

    for child in node.children:
        if child.type == "dotted_name" and child != node.children[1]:
            text = _node_text(child)
            if text:
                names.append(text)
        elif child.type == "aliased_import":
            name_node = child.child_by_field_name("name")
            alias_node = child.child_by_field_name("alias")
            text = _node_text(name_node)
            if text:
                names.append(text)
            from_alias = _node_text(alias_node)
        elif child.type == "wildcard_import":
            names.append("*")

    return [
        ImportInfo(
            module=module_name,
            names=names,
            alias=from_alias,
            is_relative=is_relative,
            level=level,
        )
    ]


def _extract_from_module(node: Node) -> tuple[str | None, int]:
    """Extract module name and relative level from import_from."""
    level = 0
    module_name: str | None = None

    past_from = False
    for child in node.children:
        text = _node_text(child)
        if text == "from":
            past_from = True
            continue
        if text == "import":
            break
        if past_from:
            level, module_name = _parse_import_source(child, text, level, module_name)

    return module_name, level


def _parse_import_source(
    child: Node,
    text: str | None,
    level: int,
    module_name: str | None,
) -> tuple[int, str | None]:
    """Parse the source part of a from-import."""
    if child.type == "relative_import":
        for sub in child.children:
            sub_text = _node_text(sub)
            if sub_text and all(c == "." for c in sub_text):
                level = len(sub_text)
            elif sub.type == "dotted_name":
                module_name = sub_text
    elif child.type == "dotted_name":
        module_name = text
    return level, module_name


def _extract_variable(node: Node) -> VariableInfo | None:
    """Extract a module-level variable from an assignment node."""
    if node.type == "expression_statement":
        expr = node.children[0] if node.children else None
        if expr is not None and expr.type == "assignment":
            return _extract_assignment(expr)
    return None


def _extract_assignment(node: Node) -> VariableInfo | None:
    """Extract variable info from an assignment node."""
    left = node.child_by_field_name("left")
    right = node.child_by_field_name("right")
    type_node = node.child_by_field_name("type")

    name = _node_text(left)
    if name is None:
        return None

    annotation = _node_text(type_node)
    value_repr = _node_text(right)
    # Truncate long values
    if value_repr and len(value_repr) > _MAX_VALUE_REPR_LEN:
        value_repr = value_repr[: _MAX_VALUE_REPR_LEN - 3] + "..."

    return VariableInfo(
        name=name,
        annotation=annotation,
        value_repr=value_repr,
        line=node.start_point.row + 1,
    )


def _extract_all_exports(node: Node) -> list[str] | None:
    """Extract __all__ list if present in the module."""
    for child in node.children:
        if child.type == "expression_statement":
            expr = child.children[0] if child.children else None
            if expr is not None and expr.type == "assignment":
                left = expr.child_by_field_name("left")
                right = expr.child_by_field_name("right")
                if _node_text(left) == "__all__" and right is not None:
                    return _parse_all_list(right)
    return None


def _parse_all_list(node: Node) -> list[str]:
    """Parse a list literal for __all__."""
    names: list[str] = []
    if node.type == "list":
        for child in node.children:
            if child.type == "string":
                text = _node_text(child)
                if text:
                    names.append(_unquote(text))
    return names


# ─── Main extraction ─────────────────────────────────────────────────────────


def extract_module_info(path: Path) -> ModuleInfo:
    """Extract full module information from a Python file.

    Parses the file using tree-sitter and extracts all functions,
    classes, imports, variables, and the module docstring.

    Args:
        path: Path to a .py file.

    Returns:
        ModuleInfo with all extracted metadata.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file is not a .py file.

    Example:
        >>> from pathlib import Path
        >>> mod = extract_module_info(Path("my_module.py"))
        >>> mod.path.name
        'my_module.py'
    """
    tree = parse_file(path)
    root = tree.root_node

    docstring = _extract_docstring(root)
    all_exports = _extract_all_exports(root)

    functions: list[FunctionInfo] = []
    classes: list[ClassInfo] = []
    imports: list[ImportInfo] = []
    variables: list[VariableInfo] = []

    for child in root.children:
        if child.type == "function_definition":
            functions.append(_extract_function(child))
        elif child.type == "decorated_definition":
            _process_decorated(child, functions, classes)
        elif child.type == "class_definition":
            classes.append(_extract_class(child))
        elif child.type in (
            "import_statement",
            "import_from_statement",
            "future_import_statement",
        ):
            imports.extend(_extract_imports(child))
        elif child.type == "expression_statement":
            var = _extract_variable(child)
            if var is not None and var.name != "__all__":
                variables.append(var)

    return ModuleInfo(
        path=path.resolve(),
        docstring=docstring,
        functions=functions,
        classes=classes,
        imports=imports,
        variables=variables,
        all_exports=all_exports,
    )


def _process_decorated(
    node: Node,
    functions: list[FunctionInfo],
    classes: list[ClassInfo],
) -> None:
    """Process a decorated_definition node."""
    for child in node.children:
        if child.type == "function_definition":
            func = _extract_function(child)
            func = func.model_copy(
                update={
                    "decorators": _extract_decorators(node),
                    "kind": _classify_function(_extract_decorators(node), "module"),
                }
            )
            functions.append(func)
        elif child.type == "class_definition":
            cls = _extract_class(child)
            cls = cls.model_copy(update={"decorators": _extract_decorators(node)})
            classes.append(cls)
