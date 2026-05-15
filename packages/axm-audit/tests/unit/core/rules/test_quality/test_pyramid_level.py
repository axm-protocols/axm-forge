"""Unit tests for PyramidLevelRule (R1+R2+R3 soft-signal core) and helpers.

Merged from:
- test_pyramid_level_core.py (rule registration + classify_level table)
- test_pyramid_cyclic_fixture.py (fixture cycle termination via _shared)
"""

from __future__ import annotations

import ast
import textwrap

import pytest

from axm_audit.core.rules.base import get_registry
from axm_audit.core.rules.test_quality._shared import fixture_does_io
from axm_audit.core.rules.test_quality.pyramid_level import (
    PyramidLevelRule,
    classify_level,
    has_in_package_subprocess_invocation,
)


def _run_call(source: str) -> ast.Call:
    module = ast.parse(source)
    calls = [node for node in ast.walk(module) if isinstance(node, ast.Call)]
    assert calls
    return calls[-1]


def test_in_package_subprocess_detects_uv_run_declared_script() -> None:
    source = """
UV_BIN = "uv"

def test_runs_declared_script():
    subprocess.run([UV_BIN, "run", "axm-audit", "audit"])
"""

    assert has_in_package_subprocess_invocation(
        call=_run_call(source),
        module_ast=ast.parse(source),
        project_scripts={"axm-audit"},
    )


def test_in_package_subprocess_detects_python_module_submodule() -> None:
    source = """
def test_runs_declared_module_submodule():
    subprocess.run([sys.executable, "-m", "axm_init.cli", "--help"])
"""

    assert has_in_package_subprocess_invocation(
        call=_run_call(source),
        module_ast=ast.parse(source),
        project_scripts={"axm-init"},
    )


def test_in_package_subprocess_ignores_plumbing_only_commands() -> None:
    sources = [
        'subprocess.run(["git", "init"])',
        'subprocess.run(["pip", "install", "-e", "."])',
        'subprocess.run(["python", "-c", "print(1)"])',
        'subprocess.run(["uv", "venv"])',
    ]

    for source in sources:
        module_ast = ast.parse(source)
        assert not has_in_package_subprocess_invocation(
            call=_run_call(source),
            module_ast=module_ast,
            project_scripts={"axm-audit"},
        )


def test_in_package_subprocess_resolves_constants_and_local_cmd_binding() -> None:
    source = """
BIN = "axm-audit"

def test_runs_bound_command():
    sub = "audit"
    cmd = [BIN, sub]
    subprocess.run(cmd)
"""

    assert has_in_package_subprocess_invocation(
        call=_run_call(source),
        module_ast=ast.parse(source),
        project_scripts={"axm-audit"},
    )


def test_rule_registered() -> None:
    registry = get_registry()
    bucket = registry.get("test_quality", [])
    classes = {item if isinstance(item, type) else type(item) for item in bucket}
    assert PyramidLevelRule in classes


def test_classify_level_e2e_requires_in_package_subprocess() -> None:
    level, reason = classify_level(
        has_real_io=False,
        has_subprocess=True,
        has_in_package_subprocess=False,
        imports_public=True,
        imports_internal=False,
    )

    assert level == "unit"
    assert reason == "public API import, no real I/O (pure function unit test)"


def test_classify_level_in_package_subprocess_wins() -> None:
    level, reason = classify_level(
        has_real_io=True,
        has_subprocess=True,
        has_in_package_subprocess=True,
        imports_public=True,
        imports_internal=True,
    )

    assert level == "e2e"
    assert "CLI" in reason


@pytest.mark.parametrize(
    ("signals", "expected"),
    [
        (
            {
                "has_real_io": False,
                "has_subprocess": True,
                "has_in_package_subprocess": False,
                "imports_public": False,
                "imports_internal": False,
            },
            "unit",
        ),
        (
            {
                "has_real_io": True,
                "has_subprocess": True,
                "has_in_package_subprocess": False,
                "imports_public": True,
                "imports_internal": True,
            },
            "integration",
        ),
        (
            {
                "has_real_io": False,
                "has_subprocess": True,
                "has_in_package_subprocess": True,
                "imports_public": False,
                "imports_internal": False,
            },
            "e2e",
        ),
        (
            {
                "has_real_io": True,
                "has_subprocess": True,
                "has_in_package_subprocess": True,
                "imports_public": True,
                "imports_internal": True,
            },
            "e2e",
        ),
        (
            {
                "has_real_io": False,
                "has_subprocess": False,
                "has_in_package_subprocess": False,
                "imports_public": True,
                "imports_internal": False,
            },
            "unit",
        ),
        (
            {
                "has_real_io": True,
                "has_subprocess": False,
                "has_in_package_subprocess": False,
                "imports_public": True,
                "imports_internal": False,
            },
            "integration",
        ),
        (
            {
                "has_real_io": True,
                "has_subprocess": False,
                "has_in_package_subprocess": False,
                "imports_public": False,
                "imports_internal": True,
            },
            "integration",
        ),
        (
            {
                "has_real_io": True,
                "has_subprocess": False,
                "has_in_package_subprocess": False,
                "imports_public": False,
                "imports_internal": False,
            },
            "integration",
        ),
        (
            {
                "has_real_io": False,
                "has_subprocess": False,
                "has_in_package_subprocess": False,
                "imports_public": False,
                "imports_internal": True,
            },
            "unit",
        ),
        (
            {
                "has_real_io": False,
                "has_subprocess": False,
                "has_in_package_subprocess": False,
                "imports_public": False,
                "imports_internal": False,
            },
            "unit",
        ),
    ],
)
def test_classify_level_8_branches_table_driven(
    signals: dict[str, bool],
    expected: str,
) -> None:
    level, reason = classify_level(**signals)
    assert level == expected
    assert reason


def test_cyclic_fixture_graph_terminates() -> None:
    """AC3: cyclic fixture graph terminates via visited-set short-circuit."""
    src = textwrap.dedent(
        """
        def fix_a(fix_b):
            return fix_b

        def fix_b(fix_a):
            return fix_a
        """
    )
    tree = ast.parse(src)
    fixtures = {
        node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)
    }
    visited: set[str] = set()

    result = fixture_does_io("fix_a", fixtures, visited, 0)

    assert result is False
    assert "fix_a" in visited
    assert "fix_b" in visited
