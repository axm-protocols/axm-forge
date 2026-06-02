"""Unit tests for PyramidLevelRule (R1+R2+R3 soft-signal core) and helpers.

Merged from:
- test_pyramid_level_core.py (rule registration + classify_level table)
- test_pyramid_cyclic_fixture.py (fixture cycle termination via _shared)
"""

from __future__ import annotations

import ast
import textwrap
from pathlib import Path

import pytest

from axm_audit.core.rules.base import get_registry
from axm_audit.core.rules.test_quality._shared import fixture_does_io
from axm_audit.core.rules.test_quality.pyramid_level import (
    PyramidLevelRule,
    classify_level,
    has_in_package_subprocess_invocation,
    scan_test_file,
)


def _run_call(source: str) -> ast.Call:
    module = ast.parse(source)
    calls = [node for node in ast.walk(module) if isinstance(node, ast.Call)]
    assert calls
    return calls[-1]


@pytest.mark.parametrize(
    ("source", "project_scripts"),
    [
        pytest.param(
            """
UV_BIN = "uv"

def test_runs_declared_script():
    subprocess.run([UV_BIN, "run", "axm-audit", "audit"])
""",
            {"axm-audit"},
            id="uv_run_declared_script",
        ),
        pytest.param(
            """
def test_runs_declared_module_submodule():
    subprocess.run([sys.executable, "-m", "axm_init.cli", "--help"])
""",
            {"axm-init"},
            id="python_module_submodule",
        ),
        pytest.param(
            """
BIN = "axm-audit"

def test_runs_bound_command():
    sub = "audit"
    cmd = [BIN, sub]
    subprocess.run(cmd)
""",
            {"axm-audit"},
            id="resolves_constants_and_local_cmd_binding",
        ),
    ],
)
def test_in_package_subprocess_detects(source: str, project_scripts: set[str]) -> None:
    assert has_in_package_subprocess_invocation(
        call=_run_call(source),
        module_ast=ast.parse(source),
        project_scripts=project_scripts,
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


def test_in_package_subprocess_tolerates_non_resolvable_argv_elements() -> None:
    """Regression: a non-resolvable element (e.g. ``str(tmp_path)``) must not
    abort the whole argv reconstruction — the remaining tokens are enough to
    detect the in-package CLI invocation."""
    source = """
def test_runs_with_dynamic_path(tmp_path):
    subprocess.run(
        ["uv", "run", "axm-audit", "audit", str(tmp_path), "--category", "structure"]
    )
"""

    module_ast = ast.parse(source)
    run_call = next(
        node
        for node in ast.walk(module_ast)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "run"
    )
    assert has_in_package_subprocess_invocation(
        call=run_call,
        module_ast=module_ast,
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


# ── parametrize-vs-fixture disambiguation (axm-1797) ──────────────────


def _scan_funcs(src: str, tmp_path: Path) -> dict[str, object]:
    """Lay out a tiny package, write *src* under ``tests/unit/`` and scan it.

    Returns ``{func_name: Finding}`` for every classified ``test_*`` function.
    Placing the module under ``tests/unit/`` makes its folder-derived level
    ``unit`` so a classified ``unit`` verdict produces no mismatch.
    """
    body = textwrap.dedent(src)
    pkg_root = tmp_path / "pkg"
    src_dir = pkg_root / "src" / "pkg"
    tests_dir = pkg_root / "tests"
    unit_dir = tests_dir / "unit"
    src_dir.mkdir(parents=True)
    unit_dir.mkdir(parents=True)
    (src_dir / "__init__.py").write_text("")
    test_file = unit_dir / "test_x.py"
    test_file.write_text(body)
    findings = scan_test_file(
        test_file=test_file,
        tree=ast.parse(body),
        pkg_root=pkg_root,
        pkg_prefixes={"pkg"},
        init_all=None,
        tests_dir=tests_dir,
    )
    return {f.function: f for f in findings}


def test_parametrized_path_arg_not_io_fixture(tmp_path: Path) -> None:
    """AC1, AC4: a direct ``@parametrize("pdf_path", ...)`` argname is not
    treated as an I/O fixture even though it matches the ``_path`` suffix."""
    findings = _scan_funcs(
        """
        import pytest

        @pytest.mark.parametrize("pdf_path", ["", "   "])
        def test_blank_pdf_path_rejected(pdf_path):
            assert pdf_path.strip() == ""
        """,
        tmp_path,
    )
    finding = findings["test_blank_pdf_path_rejected"]
    assert finding.level == "unit"
    assert "fixture-arg:pdf_path" not in finding.io_signals


def test_parametrized_multiarg_string_form(tmp_path: Path) -> None:
    """AC1: comma-joined argnames string form splits into individual
    parametrized names, none of which emit a fixture signal."""
    findings = _scan_funcs(
        """
        import pytest

        @pytest.mark.parametrize("a_path,b_dir", [("x", "y")])
        def test_two_paths(a_path, b_dir):
            assert a_path != b_dir
        """,
        tmp_path,
    )
    sigs = findings["test_two_paths"].io_signals
    assert "fixture-arg:a_path" not in sigs
    assert "fixture-arg:b_dir" not in sigs


def test_parametrized_list_form_argnames(tmp_path: Path) -> None:
    """AC1: list-of-strings argnames form is supported the same way."""
    findings = _scan_funcs(
        """
        import pytest

        @pytest.mark.parametrize(["repo_path", "cfg_file"], [("r", "c")])
        def test_list_form(repo_path, cfg_file):
            assert repo_path != cfg_file
        """,
        tmp_path,
    )
    sigs = findings["test_list_form"].io_signals
    assert "fixture-arg:repo_path" not in sigs
    assert "fixture-arg:cfg_file" not in sigs


def test_indirect_parametrize_keeps_fixture_signal(tmp_path: Path) -> None:
    """AC2: ``indirect=True`` routes the arg through a fixture, so the
    fixture signal is retained and the test is classified integration."""
    findings = _scan_funcs(
        """
        import pytest

        @pytest.mark.parametrize("tmp_path", ["x"], indirect=True)
        def test_indirect(tmp_path):
            tmp_path.write_text("hi")
        """,
        tmp_path,
    )
    finding = findings["test_indirect"]
    assert "fixture-arg:tmp_path" in finding.io_signals
    assert finding.level == "integration"


def test_indirect_subset_keeps_only_listed(tmp_path: Path) -> None:
    """AC2: ``indirect=["a_path"]`` keeps the fixture signal only for the
    listed arg; the other parametrized arg is still neutralized."""
    findings = _scan_funcs(
        """
        import pytest

        @pytest.mark.parametrize(
            ["a_path", "b_dir"], [("a", "b")], indirect=["a_path"]
        )
        def test_subset(a_path, b_dir):
            assert a_path != b_dir
        """,
        tmp_path,
    )
    sigs = findings["test_subset"].io_signals
    assert "fixture-arg:a_path" in sigs
    assert "fixture-arg:b_dir" not in sigs


def test_nonparametrized_io_fixture_unaffected(tmp_path: Path) -> None:
    """AC3: a genuine non-parametrized I/O fixture argument keeps emitting
    its signal and stays classified as integration."""
    findings = _scan_funcs(
        """
        def test_plain(tmp_path):
            tmp_path.write_text("data")
        """,
        tmp_path,
    )
    finding = findings["test_plain"]
    assert "fixture-arg:tmp_path" in finding.io_signals
    assert finding.level == "integration"
