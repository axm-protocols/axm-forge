from __future__ import annotations

import ast
from dataclasses import dataclass
from fnmatch import fnmatchcase

__all__ = [
    "CREDENTIAL_LAYER_MODULE_PATTERNS",
    "CREDENTIAL_NAME_PATTERNS",
    "EnvCredentialValueRead",
    "find_env_credential_value_reads",
    "is_credential_env_var",
    "is_credential_layer_module",
]

# Shell-style patterns keep the policy readable and easy to extend.
CREDENTIAL_NAME_PATTERNS: tuple[str, ...] = (
    "*_API_KEY",
    "*_ACCESS_KEY",
    "*_AUTH_TOKEN",
    "*_CREDENTIAL",
    "*_CREDENTIALS",
    "*_PASSWORD",
    "*_SECRET",
    "*_TOKEN",
)

# The catalogue owns credential resolution throughout this module namespace.
CREDENTIAL_LAYER_MODULE_PATTERNS: tuple[str, ...] = (
    "axm_vault",
    "axm_vault.*",
)


@dataclass(frozen=True, slots=True)
class EnvCredentialValueRead:
    """A credential environment read whose value is consumed by the module."""

    lineno: int
    env_var: str
    module_path: str


def is_credential_env_var(name: str) -> bool:
    """Return whether an environment variable name denotes a credential."""
    normalized = name.upper()
    return any(fnmatchcase(normalized, pattern) for pattern in CREDENTIAL_NAME_PATTERNS)


def is_credential_layer_module(module_path: str) -> bool:
    """Return whether a dotted path belongs to the credential layer."""
    return any(
        fnmatchcase(module_path, pattern)
        for pattern in CREDENTIAL_LAYER_MODULE_PATTERNS
    )


def find_env_credential_value_reads(
    tree: ast.AST,
    *,
    module_path: str,
) -> list[EnvCredentialValueRead]:
    """Find credential environment reads used as values rather than guards."""
    parents = _parent_map(tree)
    reads = (
        EnvCredentialValueRead(
            lineno=node.lineno,
            env_var=env_var,
            module_path=module_path,
        )
        for node in ast.walk(tree)
        if isinstance(node, (ast.Call, ast.Subscript))
        and (env_var := _environment_variable(node)) is not None
        and is_credential_env_var(env_var)
        and not _is_boolean_only_read(node, parents)
    )
    return sorted(reads, key=lambda read: read.lineno)


def _parent_map(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    return {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }


def _environment_variable(node: ast.AST) -> str | None:
    if isinstance(node, ast.Call):
        return _call_environment_variable(node)
    if isinstance(node, ast.Subscript) and _is_os_environ(node.value):
        return _string_literal(node.slice)
    return None


def _call_environment_variable(node: ast.Call) -> str | None:
    if not node.args or not _is_environment_getter(node.func):
        return None
    return _string_literal(node.args[0])


def _is_environment_getter(node: ast.AST) -> bool:
    if not isinstance(node, ast.Attribute):
        return False
    if node.attr == "getenv":
        return isinstance(node.value, ast.Name) and node.value.id == "os"
    return node.attr == "get" and _is_os_environ(node.value)


def _is_os_environ(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "environ"
        and isinstance(node.value, ast.Name)
        and node.value.id == "os"
    )


def _string_literal(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _is_boolean_only_read(
    node: ast.AST,
    parents: dict[ast.AST, ast.AST],
) -> bool:
    parent = parents.get(node)
    if isinstance(parent, ast.UnaryOp) and isinstance(parent.op, ast.Not):
        return True
    if isinstance(parent, ast.Assert) and parent.test is node:
        return True
    if isinstance(parent, (ast.If, ast.IfExp, ast.While)) and parent.test is node:
        return True
    return _is_bool_call(parent, node)


def _is_bool_call(parent: ast.AST | None, node: ast.AST) -> bool:
    return (
        isinstance(parent, ast.Call)
        and isinstance(parent.func, ast.Name)
        and parent.func.id == "bool"
        and len(parent.args) == 1
        and parent.args[0] is node
    )
