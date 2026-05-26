"""Detect ``@overload`` groups for a given symbol in a module."""

from __future__ import annotations

import libcst as cst

from axm_anvil._cst.visitors import _dotted_name

__all__ = ["_detect_overload_group"]


def _iter_typing_import_names(
    tree: cst.Module,
) -> list[cst.ImportAlias]:
    """Yield ``ImportAlias`` nodes from every ``from typing import ...`` line."""
    result: list[cst.ImportAlias] = []
    for stmt in tree.body:
        if not isinstance(stmt, cst.SimpleStatementLine):
            continue
        for inner in stmt.body:
            if not isinstance(inner, cst.ImportFrom):
                continue
            module = _dotted_name(inner.module) if inner.module else ""
            if module != "typing":
                continue
            if isinstance(inner.names, cst.ImportStar):
                continue
            result.extend(inner.names)
    return result


def _overload_alias_name(alias: cst.ImportAlias) -> str | None:
    """Return the local name bound to ``typing.overload`` for ``alias``, or ``None``."""
    if not isinstance(alias.name, cst.Name) or alias.name.value != "overload":
        return None
    if alias.asname is not None and isinstance(alias.asname.name, cst.Name):
        return alias.asname.name.value
    return "overload"


def _collect_overload_aliases(tree: cst.Module) -> set[str]:
    """Return the set of local names bound to ``typing.overload``.

    Handles ``from typing import overload`` and
    ``from typing import overload as _ov``. The bare ``typing.overload``
    attribute form is matched separately by the decorator check.
    """
    return {
        name
        for alias in _iter_typing_import_names(tree)
        if (name := _overload_alias_name(alias)) is not None
    }


def _is_overload_decorator(decorator: cst.Decorator, aliases: set[str]) -> bool:
    node: cst.BaseExpression = decorator.decorator
    if isinstance(node, cst.Call):
        node = node.func
    if isinstance(node, cst.Name):
        return node.value in aliases
    if isinstance(node, cst.Attribute):
        return _dotted_name(node) == "typing.overload"
    return False


def _detect_overload_group(tree: cst.Module, symbol_name: str) -> list[cst.FunctionDef]:
    """Return the ordered overload group for ``symbol_name``.

    Includes every top-level ``FunctionDef`` with that name when at
    least one is decorated with ``@overload`` (or ``@typing.overload``
    or a resolved alias). Returns ``[]`` otherwise.
    """
    aliases = _collect_overload_aliases(tree)
    funcs = [
        stmt
        for stmt in tree.body
        if isinstance(stmt, cst.FunctionDef) and stmt.name.value == symbol_name
    ]
    if not funcs:
        return []
    has_overload = any(
        _is_overload_decorator(dec, aliases)
        for func in funcs
        for dec in func.decorators
    )
    if not has_overload:
        return []
    return funcs
