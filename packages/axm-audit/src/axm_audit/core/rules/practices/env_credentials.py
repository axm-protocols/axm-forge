from __future__ import annotations

import ast
from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path

from axm_audit.core.rules._helpers import (
    get_python_files,
    iter_src_dirs,
    parse_file_safe,
)
from axm_audit.core.rules.base import ProjectRule, register_rule
from axm_audit.models.results import CheckResult, Severity

__all__ = [
    "CREDENTIAL_LAYER_MODULE_PATTERNS",
    "CREDENTIAL_NAME_PATTERNS",
    "EnvCredentialValueRead",
    "EnvCredentialsRule",
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


def _module_constant_env_names(tree: ast.AST) -> dict[str, str]:
    """Return literal string assignments made directly in a module."""
    if not isinstance(tree, ast.Module):
        return {}

    names: dict[str, str] = {}
    for statement in tree.body:
        if not isinstance(statement, ast.Assign):
            continue
        value = _string_literal(statement.value)
        if value is None:
            continue
        names.update(
            (target.id, value)
            for target in statement.targets
            if isinstance(target, ast.Name)
        )
    return names


def find_env_credential_value_reads(
    tree: ast.AST,
    *,
    module_path: str,
    class_attribute_names: dict[str, set[str]] | None = None,
    class_attribute_names_by_class: dict[tuple[str, str], set[str]] | None = None,
) -> list[EnvCredentialValueRead]:
    """Find credential environment reads used as values rather than guards."""
    module_constants = _module_constant_env_names(tree)
    parents = _parent_map(tree)
    reads: list[EnvCredentialValueRead] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Call, ast.Subscript)):
            continue
        if _is_boolean_only_read(node, parents):
            continue
        env_vars = _environment_variables(
            node,
            module_constants,
            class_attribute_names or {},
            class_attribute_names_by_class,
            parents,
        )
        reads.extend(
            EnvCredentialValueRead(
                lineno=node.lineno,
                env_var=env_var,
                module_path=module_path,
            )
            for env_var in sorted(env_vars)
            if is_credential_env_var(env_var)
        )
    return sorted(reads, key=lambda read: (read.lineno, read.env_var))


@register_rule("practices")
class EnvCredentialsRule(ProjectRule):
    """Detect direct reads of credential values from the environment."""

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule."""
        return "PRACTICE_ENV_CREDENTIAL_READ"

    def check(self, project_path: Path) -> CheckResult:
        """Report credential environment reads used as values in source code."""
        early = self.check_src(project_path)
        if early is not None:
            return early

        violations: list[dict[str, str | int]] = []
        for src_dir in iter_src_dirs(project_path):
            self._collect_violations(src_dir, violations)

        count = len(violations)
        passed = count == 0
        text_lines = [
            f"• {violation['file']}:{violation['line']}: "
            f"direct credential environment read ({violation['env_var']})"
            for violation in violations
        ]
        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=f"{count} credential environment read(s) found",
            severity=Severity.WARNING if not passed else Severity.INFO,
            score=max(0, 100 - count * 15),
            details={"violations": violations},
            text="\n".join(text_lines) if text_lines else None,
            fix_hint=(
                "Resolve credentials through the axm-vault credential catalogue "
                "and its axm.credentials entry-point group"
            )
            if not passed
            else None,
        )

    @staticmethod
    def _collect_violations(
        src_dir: Path,
        violations: list[dict[str, str | int]],
    ) -> None:
        """Collect direct credential reads from one source root."""
        modules: list[tuple[Path, str, ast.AST]] = []
        for path in get_python_files(src_dir):
            relative_path = path.relative_to(src_dir)
            if _is_test_module(relative_path):
                continue
            module_path = ".".join(relative_path.with_suffix("").parts)
            if is_credential_layer_module(module_path):
                continue
            parsed_tree = parse_file_safe(path)
            if parsed_tree is not None:
                modules.append((relative_path, module_path, parsed_tree))

        trees = [module_tree for _, _, module_tree in modules]
        class_attribute_names = _class_attribute_env_names(trees)
        class_attribute_names_by_class = _class_scoped_attribute_env_names(trees)
        for relative_path, module_path, module_tree in modules:
            violations.extend(
                {
                    "file": relative_path.as_posix(),
                    "line": read.lineno,
                    "env_var": read.env_var,
                }
                for read in find_env_credential_value_reads(
                    module_tree,
                    module_path=module_path,
                    class_attribute_names=class_attribute_names,
                    class_attribute_names_by_class=class_attribute_names_by_class,
                )
            )


def _is_test_module(relative_path: Path) -> bool:
    """Return whether a source-relative path denotes test code."""
    return relative_path.name.startswith("test_") or any(
        part.startswith("tests") for part in relative_path.parts[:-1]
    )


def _parent_map(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    return {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }


def _class_attribute_env_names(
    trees: list[ast.AST],
) -> dict[str, set[str]]:
    """Index non-empty literal class attributes across parsed modules."""
    names: dict[str, set[str]] = {}
    for tree in trees:
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            for attribute, value in _class_literal_env_names(node):
                names.setdefault(attribute, set()).add(value)
    return names


def _class_scoped_attribute_env_names(
    trees: list[ast.AST],
) -> dict[tuple[str, str], set[str]]:
    definitions = _unique_class_definitions(trees)
    bases = {name: _base_class_names(node) for name, node in definitions.items()}
    direct = {
        name: _literal_names_by_attribute(node) for name, node in definitions.items()
    }
    resolved: dict[tuple[str, str], set[str]] = {}
    for owner in definitions:
        for class_name in _descendant_names(owner, bases):
            for attribute, values in direct[class_name].items():
                resolved.setdefault((owner, attribute), set()).update(values)
    return resolved


def _unique_class_definitions(
    trees: list[ast.AST],
) -> dict[str, ast.ClassDef]:
    candidates = [
        node
        for tree in trees
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef)
    ]
    counts: dict[str, int] = {}
    for node in candidates:
        counts[node.name] = counts.get(node.name, 0) + 1
    return {node.name: node for node in candidates if counts[node.name] == 1}


def _base_class_names(node: ast.ClassDef) -> set[str]:
    return {
        base.id if isinstance(base, ast.Name) else base.attr
        for base in node.bases
        if isinstance(base, (ast.Name, ast.Attribute))
    }


def _descendant_names(
    owner: str,
    bases: dict[str, set[str]],
) -> set[str]:
    descendants = {owner}
    while additions := {
        name
        for name, parent_names in bases.items()
        if name not in descendants and parent_names & descendants
    }:
        descendants.update(additions)
    return descendants


def _literal_names_by_attribute(
    node: ast.ClassDef,
) -> dict[str, set[str]]:
    names: dict[str, set[str]] = {}
    for attribute, value in _class_literal_env_names(node):
        names.setdefault(attribute, set()).add(value)
    return names


def _class_literal_env_names(
    node: ast.ClassDef,
) -> list[tuple[str, str]]:
    assignments: list[tuple[str, str]] = []
    for statement in node.body:
        targets: list[ast.expr]
        value_node: ast.expr | None
        if isinstance(statement, ast.Assign):
            targets = statement.targets
            value_node = statement.value
        elif isinstance(statement, ast.AnnAssign):
            targets = [statement.target]
            value_node = statement.value
        else:
            continue
        value = _string_literal(value_node) if value_node is not None else None
        if not value:
            continue
        assignments.extend(
            (target.id, value) for target in targets if isinstance(target, ast.Name)
        )
    return assignments


def _environment_variables(
    node: ast.AST,
    module_constants: dict[str, str],
    class_attribute_names: dict[str, set[str]],
    class_attribute_names_by_class: dict[tuple[str, str], set[str]] | None,
    parents: dict[ast.AST, ast.AST],
) -> set[str]:
    direct = _environment_variable(node, module_constants)
    if direct is not None:
        return {direct}

    argument = _environment_argument(node)
    attribute = _self_attribute_name(argument)
    if attribute is None:
        return set()
    if class_attribute_names_by_class is None:
        return class_attribute_names.get(attribute, set())

    class_name = _enclosing_class_name(node, parents)
    if class_name is None:
        return set()
    return class_attribute_names_by_class.get((class_name, attribute), set())


def _environment_argument(node: ast.AST) -> ast.expr | None:
    if isinstance(node, ast.Call):
        if not node.args or not _is_environment_getter(node.func):
            return None
        return node.args[0]
    if isinstance(node, ast.Subscript) and _is_os_environ(node.value):
        return node.slice
    return None


def _self_attribute_name(node: ast.expr | None) -> str | None:
    if (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "self"
    ):
        return node.attr
    return None


def _enclosing_class_name(
    node: ast.AST,
    parents: dict[ast.AST, ast.AST],
) -> str | None:
    current = parents.get(node)
    while current is not None:
        if isinstance(current, ast.ClassDef):
            return current.name
        current = parents.get(current)
    return None


def _environment_variable(
    node: ast.AST,
    module_constants: dict[str, str],
) -> str | None:
    if isinstance(node, ast.Call):
        literal = _call_environment_variable(node)
        if literal is not None:
            return literal
        if not node.args or not _is_environment_getter(node.func):
            return None
        argument = node.args[0]
    elif isinstance(node, ast.Subscript) and _is_os_environ(node.value):
        argument = node.slice
    else:
        return None

    literal = _string_literal(argument)
    if literal is not None:
        return literal
    if isinstance(argument, ast.Name):
        return module_constants.get(argument.id)
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
