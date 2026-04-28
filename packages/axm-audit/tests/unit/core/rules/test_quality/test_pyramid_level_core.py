"""Unit tests for PyramidLevelRule (R1+R2+R3 soft-signal core)."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from axm_audit.core.registry import get_registry
from axm_audit.core.rules.test_quality.pyramid_level import (
    Finding,
    PyramidCheckResult,
    PyramidLevelRule,
    _classify_level,
)
from axm_audit.core.severity import Severity


def _write(root: Path, relpath: str, body: str) -> Path:
    p = root / relpath
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(dedent(body).lstrip())
    return p


def _check(tmp_path: Path) -> PyramidCheckResult:
    return PyramidLevelRule().check(tmp_path)


def _first_finding(result: PyramidCheckResult) -> Finding:
    findings = list(result.findings)
    assert findings, f"expected at least one finding, got {result!r}"
    return findings[0]


def test_rule_registered() -> None:
    registry = get_registry()
    bucket = registry.get("test_quality", [])
    classes = {item if isinstance(item, type) else type(item) for item in bucket}
    assert PyramidLevelRule in classes


def test_r1_import_httpx_unused_stays_unit(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "tests/integration/test_foo.py",
        """
        import httpx  # noqa: F401

        def test_x():
            assert 1 + 1 == 2
        """,
    )
    finding = _first_finding(_check(tmp_path))
    assert finding.level == "unit"
    assert finding.has_real_io is False
    assert "imports httpx" not in finding.io_signals


def test_r1_import_httpx_referenced_becomes_integration(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "tests/unit/test_foo.py",
        """
        import httpx

        def test_x():
            httpx.get("http://example.com")
        """,
    )
    finding = _first_finding(_check(tmp_path))
    assert finding.level == "integration"
    assert finding.has_real_io is True
    assert "imports httpx" in finding.io_signals


def test_r2_public_only_no_io_is_unit(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "src/pkg/__init__.py",
        """
        __all__ = ["public_fn"]

        def public_fn():
            return 1
        """,
    )
    _write(
        tmp_path,
        "tests/integration/test_foo.py",
        """
        from pkg import public_fn

        def test_x():
            assert public_fn() == 1
        """,
    )
    finding = _first_finding(_check(tmp_path))
    assert finding.level == "unit"
    assert "pure function" in finding.reason


def test_r3_attr_write_text_per_function(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "tests/unit/test_foo.py",
        """
        def test_x(path):
            path.write_text("x")
        """,
    )
    finding = _first_finding(_check(tmp_path))
    assert "attr:.write_text()" in finding.io_signals
    assert finding.level == "integration"


def test_r3_transitive_helper_at_depth_2(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "tests/unit/test_foo.py",
        """
        def helper_b(p):
            p.mkdir()

        def helper_a(p):
            helper_b(p)

        def test_x(p):
            helper_a(p)
        """,
    )
    finding = _first_finding(_check(tmp_path))
    assert "attr:.mkdir()" in finding.io_signals


def test_r3_transitive_helper_depth_guard(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "tests/unit/test_foo.py",
        """
        def helper_d(p):
            p.write_text("x")

        def helper_c(p):
            helper_d(p)

        def helper_b(p):
            helper_c(p)

        def helper_a(p):
            helper_b(p)

        def test_x(p):
            helper_a(p)
        """,
    )
    finding = _first_finding(_check(tmp_path))
    assert "attr:.write_text()" not in finding.io_signals


def test_r3_fixture_io_guard_matches_io_fixture(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "tests/unit/test_foo.py",
        """
        def test_x(tmp_path_factory):
            assert tmp_path_factory is not None
        """,
    )
    finding = _first_finding(_check(tmp_path))
    assert "fixture-arg:tmp_path_factory" in finding.io_signals
    assert finding.has_real_io is True


def test_r3_fixture_io_guard_matches_suffix(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "tests/unit/test_foo.py",
        """
        def test_x(my_pkg):
            assert my_pkg is not None
        """,
    )
    finding = _first_finding(_check(tmp_path))
    assert "fixture-arg:my_pkg" in finding.io_signals
    assert finding.has_real_io is True


def test_r3_fixture_io_guard_skips_mock_name(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "tests/integration/test_foo.py",
        """
        def test_x(mock_workspace):
            assert mock_workspace is not None
        """,
    )
    result = _check(tmp_path)
    findings = list(result.findings)
    if findings:
        assert not any(s.startswith("fixture-arg:") for s in findings[0].io_signals)


def test_r3_tmp_path_as_arg_taint(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "tests/integration/test_foo.py",
        """
        def f(p):
            return p

        def test_x(tmp_path):
            f(tmp_path / "a")
        """,
    )
    finding = _first_finding(_check(tmp_path))
    assert "tmp_path-as-arg" in finding.io_signals


def test_r3_tmp_path_aliased_reaches_call(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "tests/integration/test_foo.py",
        """
        def f(p):
            return p

        def test_x(tmp_path):
            p = tmp_path / "a"
            q = p
            f(q)
        """,
    )
    finding = _first_finding(_check(tmp_path))
    assert "tmp_path-as-arg" in finding.io_signals


def test_tmp_path_boundary_write_text(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "tests/unit/test_foo.py",
        """
        def test_x(tmp_path):
            tmp_path.write_text("x")
        """,
    )
    finding = _first_finding(_check(tmp_path))
    assert "tmp_path+write/read" in finding.io_signals
    assert finding.level == "integration"


def test_cli_runner_classifies_e2e(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "tests/unit/test_foo.py",
        """
        from typer.testing import CliRunner

        app = object()

        def test_x():
            CliRunner().invoke(app)
        """,
    )
    finding = _first_finding(_check(tmp_path))
    assert finding.has_subprocess is True
    assert finding.level == "e2e"


def test_cli_runner_name_detection(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "tests/unit/test_foo.py",
        """
        from typer.testing import CliRunner

        app = object()

        def test_x():
            runner = CliRunner()
            runner.invoke(app)
        """,
    )
    finding = _first_finding(_check(tmp_path))
    assert finding.has_subprocess is True


def test_cli_runner_fixture_direct_call_classifies_e2e(tmp_path: Path) -> None:
    """Cyclopts-style ``cli_runner(args)`` (fixture-as-callable) is e2e."""
    _write(
        tmp_path,
        "tests/e2e/test_foo.py",
        """
        def test_x(cli_runner):
            result = cli_runner(["--help"])
            assert result.exit_code == 0
        """,
    )
    finding = _first_finding(_check(tmp_path))
    assert "cli:cli_runner" in finding.io_signals
    assert finding.has_subprocess is True
    assert finding.level == "e2e"


def test_fake_fixture_with_real_io_classifies_integration(tmp_path: Path) -> None:
    """Fixture named ``fake_*`` that performs real I/O is NOT mock-neutralised."""
    _write(tmp_path, "tests/conftest.py", "")
    _write(
        tmp_path,
        "tests/integration/conftest.py",
        """
        import pytest

        @pytest.fixture
        def fake_workbook(tmp_path_factory):
            path = tmp_path_factory.mktemp('wb') / 'fake.xlsx'
            path.write_text('synthetic')
            return path
        """,
    )
    _write(
        tmp_path,
        "tests/integration/test_foo.py",
        """
        def test_x(fake_workbook):
            assert fake_workbook.exists()
        """,
    )
    finding = _first_finding(_check(tmp_path))
    assert finding.has_real_io is True
    assert finding.level == "integration"


def test_literal_str_replace_not_treated_as_io(tmp_path: Path) -> None:
    """``str.replace("a","b")`` (formatting) does not mark a test as I/O."""
    _write(
        tmp_path,
        "tests/unit/test_foo.py",
        """
        def test_x():
            value = "1.5".replace(".", ",")
            assert value == "1,5"
        """,
    )
    finding = _first_finding(_check(tmp_path))
    assert "attr:.replace()" not in finding.io_signals
    assert finding.has_real_io is False
    assert finding.level == "unit"


def test_submodule_all_public_detection(tmp_path: Path) -> None:
    _write(tmp_path, "src/pkg/__init__.py", "")
    _write(
        tmp_path,
        "src/pkg/core/__init__.py",
        """
        __all__ = ["X"]

        class X:
            pass
        """,
    )
    _write(
        tmp_path,
        "tests/integration/test_foo.py",
        """
        from pkg.core import X

        def test_x():
            assert X is not None
        """,
    )
    finding = _first_finding(_check(tmp_path))
    assert "X" in finding.imports_public
    assert "X" not in getattr(finding, "imports_internal", [])


def test_suggested_file_for_unit_rule(tmp_path: Path) -> None:
    _write(tmp_path, "src/pkg/__init__.py", "")
    _write(tmp_path, "src/pkg/core/__init__.py", "")
    _write(
        tmp_path,
        "src/pkg/core/parser.py",
        """
        def parse():
            return 1
        """,
    )
    _write(
        tmp_path,
        "tests/test_parser.py",
        """
        from pkg.core.parser import parse

        def test_x():
            assert parse() == 1
        """,
    )
    finding = _first_finding(_check(tmp_path))
    assert finding.suggested_file == "unit/core/test_parser.py"


def test_severity_warning(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "tests/unit/test_foo.py",
        """
        def test_x(tmp_path):
            tmp_path.write_text("x")
        """,
    )
    result = _check(tmp_path)
    finding = _first_finding(result)
    assert finding.severity == Severity.WARNING


def test_empty_tests_returns_pass(tmp_path: Path) -> None:
    result = PyramidLevelRule().check(tmp_path)
    assert result.passed is True
    assert result.score == 100
    assert list(result.findings) == []


@pytest.mark.parametrize(
    ("has_real_io", "has_subprocess", "imports_public", "imports_internal", "expected"),
    [
        (False, True, False, False, "e2e"),
        (True, True, True, True, "e2e"),
        (False, False, True, False, "unit"),
        (True, False, True, False, "integration"),
        (True, False, False, True, "integration"),
        (True, False, False, False, "integration"),
        (False, False, False, True, "unit"),
        (False, False, False, False, "unit"),
    ],
)
def test_classify_level_8_branches_table_driven(
    has_real_io: bool,
    has_subprocess: bool,
    imports_public: bool,
    imports_internal: bool,
    expected: str,
) -> None:
    level, reason = _classify_level(
        has_real_io=has_real_io,
        has_subprocess=has_subprocess,
        imports_public=imports_public,
        imports_internal=imports_internal,
    )
    assert level == expected
    assert reason
