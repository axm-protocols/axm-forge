"""Integration: content assertions on bundled scaffold templates (AXM-2048).

These tests harden the template config surface flagged in review
``axm-forge-2026-06-13/axm-init.md`` (F9 mypy hooks, F10 S603/S607, F11
coverage.xml, F5 action-version drift). They read the real template files
shipped under ``axm_init.templates`` via ``get_template_path`` (real I/O on the
packaged template tree) and assert on their content, so a future drift in any
template fails here.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_init.core.templates import TemplateType, get_template_path

pytestmark = pytest.mark.integration


def _read(template: TemplateType, *parts: str) -> str:
    """Read a file from the packaged *template* tree as text."""
    path = Path(get_template_path(template)).joinpath(*parts)
    return path.read_text()


def test_workspace_gitignore_has_coverage_xml() -> None:
    """AC3: the uv-workspace .gitignore ignores coverage.xml.

    Aligns with python-project/.gitignore so a scaffolded workspace does not
    commit the coverage report produced by the CI ``--cov-report=xml`` step.
    """
    content = _read(TemplateType.WORKSPACE, ".gitignore")
    assert "coverage.xml" in content.splitlines()


def test_member_tests_ignore_s603_s607() -> None:
    """AC2: workspace-member tests/* per-file-ignores include S603 and S607.

    Subprocess-based test helpers legitimately call out to processes; without
    S603/S607 in the tests ignore list every such call is a false positive.
    """
    content = _read(TemplateType.MEMBER, "pyproject.toml.jinja")
    ignore_lines = [
        line
        for line in content.splitlines()
        if '"tests/*"' in line and "per-file-ignores" not in line
    ]
    # The tests/* per-file-ignores assignment line.
    target = next(
        (line for line in content.splitlines() if line.strip().startswith('"tests/*"')),
        "",
    )
    assert "S603" in target, ignore_lines
    assert "S607" in target, ignore_lines


def test_action_versions_consistent() -> None:
    """AC4: uv-workspace and python-project CI pin the same action versions.

    Both ci.yml templates must reference the same actions/checkout and
    astral-sh/setup-uv major versions so the two scaffolds do not drift.
    """
    ws_ci = _read(TemplateType.WORKSPACE, ".github", "workflows", "ci.yml.jinja")
    std_ci = _read(TemplateType.STANDALONE, ".github", "workflows", "ci.yml.jinja")

    def _versions(content: str, action: str) -> set[str]:
        return {
            line.split(f"{action}@", 1)[1].strip()
            for line in content.splitlines()
            if f"{action}@" in line
        }

    for action in ("actions/checkout", "astral-sh/setup-uv"):
        ws_versions = _versions(ws_ci, action)
        std_versions = _versions(std_ci, action)
        assert ws_versions, f"no {action} usage in uv-workspace ci.yml"
        assert std_versions, f"no {action} usage in python-project ci.yml"
        assert ws_versions == std_versions, (action, ws_versions, std_versions)


def test_workspace_mypy_hook_is_local_per_package() -> None:
    """AC1: uv-workspace pre-commit uses a local per-package mypy hook.

    The global ``mirrors-mypy`` hook cannot resolve workspace-member deps (it
    runs at root with only ``additional_dependencies: [pydantic]``), producing
    false positives. It is replaced by a ``repo: local`` mypy hook invoked via
    ``uv run --package <pkg> mypy`` with ``pass_filenames: false``.
    """
    content = _read(TemplateType.WORKSPACE, ".pre-commit-config.yaml.jinja")
    assert "mirrors-mypy" not in content
    assert "repo: local" in content
    assert "uv run --package" in content
    assert "mypy" in content
    assert "pass_filenames: false" in content
