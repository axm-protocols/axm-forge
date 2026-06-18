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
    Finding,
    PyramidLevelRule,
    classify_level,
    has_in_package_subprocess_invocation,
    render_mismatch_text,
    scan_test_file,
)


def _classify_synthetic(source: str) -> dict[str, str]:
    """Classify every ``test_*`` function in *source* via the public scan entry.

    Drives ``scan_test_file`` against an in-memory AST (no disk writes), so the
    full signal-collection pipeline (R1..R5) runs without real I/O. Returns a
    ``{function_name: classified_level}`` mapping read off each ``Finding``.
    """
    tree = ast.parse(textwrap.dedent(source))
    pkg_root = Path("/synthetic/pkg")
    findings = scan_test_file(
        test_file=pkg_root / "tests" / "unit" / "test_synthetic.py",
        tree=tree,
        pkg_root=pkg_root,
        pkg_prefixes={"sample"},
        init_all={"public_fn"},
        tests_dir=pkg_root / "tests",
    )
    return {f.function: f.level for f in findings}


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


def _mismatch_finding(io_signals: list[str]) -> Finding:
    """Build a single mismatch Finding with the given deciding io_signals."""
    return Finding(
        path="/proj/tests/test_thing.py",
        function="test_thing",
        level="integration",
        reason="real I/O detected",
        current_level="unit",
        has_real_io=True,
        has_subprocess=False,
        io_signals=io_signals,
    )


def test_render_includes_io_signals() -> None:
    """AC1, AC3: deciding io_signals are surfaced alongside the reason."""
    finding = _mismatch_finding(["tmp_path->open", "fixture:db_session"])

    text = render_mismatch_text([finding], Path("/proj"))

    assert "real I/O detected" in text
    assert "tmp_path->open" in text
    assert "fixture:db_session" in text
    assert "signals:" in text


def test_render_omits_empty_signals() -> None:
    """AC2: an empty io_signals renders the reason with no signals fragment."""
    finding = _mismatch_finding([])

    text = render_mismatch_text([finding], Path("/proj"))

    assert "real I/O detected" in text
    assert "signals:" not in text
    assert "[]" not in text


def test_render_signal_order_stable() -> None:
    """AC3: same signal set yields identical deterministically-ordered output."""
    finding_a = _mismatch_finding(["tmp_path->open", "fixture:db_session"])
    finding_b = _mismatch_finding(["fixture:db_session", "tmp_path->open"])

    text_a = render_mismatch_text([finding_a], Path("/proj"))
    text_b = render_mismatch_text([finding_b], Path("/proj"))

    assert text_a == text_b


def test_importorskip_heavy_dep_is_integration() -> None:
    """AC1: importorskip on a heavy external dep is a real-I/O signal.

    A test that ``pytest.importorskip("mlx_audio")`` then imports the public API
    and calls a pure function must NOT be rescued to unit by R2 — the heavy
    optional dep is the integration signal.
    """
    levels = _classify_synthetic(
        """
        import pytest
        from sample import public_fn

        def test_uses_heavy_dep():
            pytest.importorskip("mlx_audio")
            assert public_fn() == 1
        """
    )

    assert levels["test_uses_heavy_dep"] == "integration"


def test_importorskip_light_dep_stays_unit() -> None:
    """AC1: importorskip on a light dep (not in the allowlist) stays unit.

    ``importorskip("click")`` is NOT a heavy ML/native dep, so it must not flip
    a pure-function public-API test to integration.
    """
    levels = _classify_synthetic(
        """
        import pytest
        from sample import public_fn

        def test_uses_light_dep():
            pytest.importorskip("click")
            assert public_fn() == 1
        """
    )

    assert levels["test_uses_light_dep"] == "unit"


def test_fully_mocked_tmp_path_is_unit() -> None:
    """AC2: residual tmp_path path-bookkeeping under full mocking stays unit.

    When every real-I/O target is patched and the only tmp_path usage is
    bookkeeping (``.exists()`` / ``.unlink()``) with no content read/write, the
    test is a unit test, not integration.
    """
    levels = _classify_synthetic(
        """
        from sample import public_fn

        def test_speak(mocker, tmp_path):
            mocker.patch("sample.open")
            mocker.patch("sample.public_fn")
            out = tmp_path / "out.wav"
            if out.exists():
                out.unlink()
        """
    )

    assert levels["test_speak"] == "unit"


def test_real_tmp_path_write_stays_integration() -> None:
    """AC2: a genuine tmp_path content write is still integration.

    An unmocked ``write_text(content)`` on a tmp_path is real I/O and must keep
    the test at integration even though tmp_path is a fixture.
    """
    levels = _classify_synthetic(
        """
        from sample import public_fn

        def test_writes_real_file(tmp_path):
            out = tmp_path / "out.txt"
            out.write_text("payload")
            assert public_fn(out) is not None
        """
    )

    assert levels["test_writes_real_file"] == "integration"


def test_no_pattern_match_verdict_unchanged() -> None:
    """AC3: a test matching neither new pattern keeps its prior verdict.

    A pure public-API unit test (no importorskip, no tmp_path) must remain
    unit — byte-identical to the pre-change behavior.
    """
    levels = _classify_synthetic(
        """
        from sample import public_fn

        def test_pure():
            assert public_fn() == 1
        """
    )

    assert levels["test_pure"] == "unit"
