from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

import pytest

_COMMAND_TOKEN = re.compile(r"\b(?:axm-audit\s+audit|axm\s+audit)\b")
_UNIFIED_COMMAND = re.compile(r"\baxm\s+audit\b")
_FENCED_BLOCK = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)


def _workflow_templates(root: Path) -> list[Path]:
    template_root = root / "packages" / "axm-init" / "src"
    return [
        path
        for path in template_root.rglob("*")
        if path.is_file()
        and path.name.endswith((".yml", ".yaml", ".yml.jinja", ".yaml.jinja"))
        and "workflows" in path.parts
    ]


def _documentation_recipes(root: Path) -> list[Path]:
    documentation_roots = (
        root / "docs",
        root / "packages" / "axm-audit" / "docs",
        root / "packages" / "axm-init" / "docs",
    )
    return [
        path
        for documentation_root in documentation_roots
        if documentation_root.is_dir()
        for path in documentation_root.rglob("*.md")
    ]


def _command_lines(path: Path, *, fenced_only: bool = False) -> list[str]:
    text = path.read_text(encoding="utf-8")
    searchable = "\n".join(_FENCED_BLOCK.findall(text)) if fenced_only else text
    return [
        line.strip() for line in searchable.splitlines() if _COMMAND_TOKEN.search(line)
    ]


@pytest.mark.integration
def test_versioned_quality_command_roles_use_unified_structured_invocation() -> None:
    """AC1: all versioned quality-command roles use axm audit --json-output."""
    root = Path(__file__).resolve().parents[4]
    role_files: dict[str, Iterable[Path]] = {
        "root workflow": (
            *sorted((root / ".github" / "workflows").glob("*.yml")),
            *sorted((root / ".github" / "workflows").glob("*.yaml")),
        ),
        "root developer commands": (root / "Makefile",),
        "scaffold workflow templates": _workflow_templates(root),
        "documentation recipes": _documentation_recipes(root),
    }

    invocations: dict[str, list[tuple[Path, str]]] = {}
    for role, paths in role_files.items():
        invocations[role] = [
            (path, line)
            for path in paths
            for line in _command_lines(
                path,
                fenced_only=role == "documentation recipes",
            )
        ]

    missing_roles = [role for role, commands in invocations.items() if not commands]
    assert not missing_roles, (
        f"quality-command roles without an auditable invocation: {missing_roles}"
    )

    violations = [
        f"{path.relative_to(root)}: {line}"
        for commands in invocations.values()
        for path, line in commands
        if not _UNIFIED_COMMAND.search(line) or "--json-output" not in line
    ]
    assert not violations, "retired or unstructured audit invocations:\n" + "\n".join(
        violations
    )
