from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from axm_audit.core.rules._helpers import (
    get_python_files,
    iter_src_dirs,
    parse_file_safe,
)
from axm_audit.core.rules.base import ProjectRule, register_rule
from axm_audit.models.results import CheckResult, Severity

__all__ = [
    "ToolSecretLocation",
    "find_tool_keyring_service_literals",
    "find_tool_session_path_literals",
    "is_auth_detection_module",
]

_AUTH_TOKENS = frozenset({"auth", "credential", "credentials"})
_KEYRING_METHODS = frozenset({"get_password", "set_password", "delete_password"})
_TOOL_PATH_PATTERNS = (
    re.compile(r"(?:^|/)~/\.(?P<tool>[^/]+)/"),
    re.compile(r"(?:^|/)\.config/(?P<tool>[^/]+)/"),
    re.compile(
        r"(?:^|/)Library/Application Support/(?P<tool>[^/]+)/",
        re.IGNORECASE,
    ),
)


@dataclass(frozen=True)
class ToolSecretLocation:
    """A literal that exposes a third-party tool's secret location."""

    kind: Literal["session_path", "keyring_service"]
    value: str
    line: int


def _words(value: str) -> tuple[str, ...]:
    return tuple(part for part in re.split(r"[^a-z0-9]+", value.casefold()) if part)


def _normalise_namespace(value: str) -> str:
    return value.casefold().replace("-", "_")


def _is_first_party_namespace(
    namespace: str,
    first_party: frozenset[str],
) -> bool:
    normalised = _normalise_namespace(namespace)
    return any(normalised == _normalise_namespace(item) for item in first_party)


def _is_first_party_value(value: str, first_party: frozenset[str]) -> bool:
    value_words = _words(value)
    for namespace in first_party:
        namespace_words = _words(namespace)
        width = len(namespace_words)
        if width and any(
            value_words[index : index + width] == namespace_words
            for index in range(len(value_words) - width + 1)
        ):
            return True
    return False


def is_auth_detection_module(module_path: str) -> bool:
    """Return whether a path contains an auth-detection namespace token."""
    path_segments = module_path.replace("\\", "/").split("/")
    if path_segments:
        path_segments[-1] = path_segments[-1].rsplit(".", maxsplit=1)[0]
    return any(
        token in _AUTH_TOKENS for segment in path_segments for token in _words(segment)
    )


def _tool_namespace(value: str) -> str | None:
    for pattern in _TOOL_PATH_PATTERNS:
        if match := pattern.search(value):
            return match.group("tool")
    return None


def _has_secret_file_shape(value: str) -> bool:
    basename = value.replace("\\", "/").rsplit("/", maxsplit=1)[-1].casefold()
    return (
        (basename.startswith("auth") and basename.endswith(".json"))
        or "credential" in basename
        or "session" in basename
        or basename.startswith("token")
        or bool(re.fullmatch(r"hosts\.ya?ml", basename))
        or basename.endswith(".keychain")
    )


def find_tool_session_path_literals(
    tree: ast.Module,
    first_party: frozenset[str],
) -> list[ToolSecretLocation]:
    """Find third-party tool session-path literals in a parsed module."""
    locations: list[ToolSecretLocation] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        namespace = _tool_namespace(node.value)
        if (
            namespace is None
            or _is_first_party_namespace(namespace, first_party)
            or not _has_secret_file_shape(node.value)
        ):
            continue
        locations.append(
            ToolSecretLocation(
                kind="session_path",
                value=node.value,
                line=node.lineno,
            )
        )
    return sorted(locations, key=lambda location: (location.line, location.value))


def _call_service_literal(call: ast.Call) -> ast.Constant | None:
    if not (
        isinstance(call.func, (ast.Name, ast.Attribute))
        and (call.func.id if isinstance(call.func, ast.Name) else call.func.attr)
        in _KEYRING_METHODS
    ):
        return None
    if call.args:
        candidate = call.args[0]
        if isinstance(candidate, ast.Constant) and isinstance(candidate.value, str):
            return candidate
    for keyword in call.keywords:
        if (
            keyword.arg == "service_name"
            and isinstance(keyword.value, ast.Constant)
            and isinstance(keyword.value.value, str)
        ):
            return keyword.value
    return None


def _security_service_literals(tree: ast.Module) -> list[ast.Constant]:
    literals: list[ast.Constant] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.List, ast.Tuple)):
            continue
        values = [
            element.value
            for element in node.elts
            if isinstance(element, ast.Constant) and isinstance(element.value, str)
        ]
        if "security" not in values or "find-generic-password" not in values:
            continue
        for index, element in enumerate(node.elts[:-1]):
            if isinstance(element, ast.Constant) and element.value in {
                "-s",
                "--service",
            }:
                candidate = node.elts[index + 1]
                if isinstance(candidate, ast.Constant) and isinstance(
                    candidate.value, str
                ):
                    literals.append(candidate)
    return literals


def find_tool_keyring_service_literals(
    tree: ast.Module,
    first_party: frozenset[str],
) -> list[ToolSecretLocation]:
    """Find third-party service literals used by keyring APIs or security."""
    literals = [
        literal
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        if (literal := _call_service_literal(node)) is not None
    ]
    literals.extend(_security_service_literals(tree))
    locations = [
        ToolSecretLocation(
            kind="keyring_service",
            value=literal.value,
            line=literal.lineno,
        )
        for literal in literals
        if isinstance(literal.value, str)
        and not _is_first_party_value(literal.value, first_party)
    ]
    return sorted(locations, key=lambda location: (location.line, location.value))


def first_party_namespaces(project: Path) -> frozenset[str]:
    """Derive namespace tokens owned by the audited project."""
    namespaces: set[str] = set()
    for src_dir in iter_src_dirs(project):
        for package_dir in src_dir.iterdir():
            if not package_dir.is_dir() or package_dir.name.startswith("."):
                continue
            package_name = package_dir.name
            namespaces.add(package_name)
            namespaces.add(package_name.split("_", maxsplit=1)[0])
    return frozenset(namespaces)


@register_rule("practices")
class ToolSecretLocationRule(ProjectRule):
    """Detect third-party secret locations embedded in auth detectors."""

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule."""
        return "PRACTICE_TOOL_SECRET_LOCATION"

    def check(self, project_path: Path) -> CheckResult:
        """Report third-party session paths and keyring service literals."""
        early = self.check_src(project_path)
        if early is not None:
            return early

        first_party = first_party_namespaces(project_path)
        findings: list[dict[str, str | int]] = []
        for src_dir in iter_src_dirs(project_path):
            self._collect_findings(src_dir, first_party, findings)

        count = len(findings)
        passed = count == 0
        text_lines = [
            f"• {finding['file']}:{finding['line']}: "
            f"{finding['kind']} ({finding['literal']})"
            for finding in findings
        ]
        return CheckResult(
            rule_id=self.rule_id,
            passed=passed,
            message=f"{count} tool secret location(s) found",
            severity=Severity.WARNING if not passed else Severity.INFO,
            score=max(0, 100 - count * 15),
            details={"findings": findings},
            metadata={"findings": findings},
            text="\n".join(text_lines) if text_lines else None,
            fix_hint=(
                "Probe the third-party tool through its supported interface instead of "
                "embedding its secret locations"
            )
            if not passed
            else None,
        )

    @staticmethod
    def _collect_findings(
        src_dir: Path,
        first_party: frozenset[str],
        findings: list[dict[str, str | int]],
    ) -> None:
        """Collect findings from auth-detection modules below one source root."""
        for path in sorted(get_python_files(src_dir)):
            relative_path = path.relative_to(src_dir)
            if not is_auth_detection_module(relative_path.as_posix()):
                continue
            tree = parse_file_safe(path)
            if tree is None:
                continue
            locations = find_tool_session_path_literals(tree, first_party)
            locations.extend(find_tool_keyring_service_literals(tree, first_party))
            findings.extend(
                {
                    "file": relative_path.as_posix(),
                    "line": location.line,
                    "kind": location.kind,
                    "literal": location.value,
                }
                for location in sorted(
                    locations,
                    key=lambda item: (item.line, item.kind, item.value),
                )
            )


__all__ += ["ToolSecretLocationRule", "first_party_namespaces"]
