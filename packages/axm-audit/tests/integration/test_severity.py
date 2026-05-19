"""Unit tests for PyramidLevelRule (R1+R2+R3 soft-signal core)."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from axm_audit.core.rules.test_quality.pyramid_level import (
    Finding,
    PyramidCheckResult,
    PyramidLevelRule,
)
from axm_audit.models.results import Severity


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


@pytest.mark.parametrize(
    ("relpath", "body", "expected_signal"),
    [
        pytest.param(
            "tests/unit/test_foo.py",
            """
            def helper_b(p):
                p.mkdir()

            def helper_a(p):
                helper_b(p)

            def test_x(p):
                helper_a(p)
            """,
            "attr:.mkdir()",
            id="transitive_helper_at_depth_2",
        ),
        pytest.param(
            "tests/integration/test_foo.py",
            """
            import subprocess

            def test_x(tmp_path):
                subprocess.run(["ls", str(tmp_path / "a")])
            """,
            "tmp_path-as-arg",
            id="tmp_path_as_arg_taint_to_io_sink",
        ),
        pytest.param(
            "tests/integration/test_foo.py",
            """
            import subprocess

            def test_x(tmp_path):
                p = tmp_path / "a"
                q = p
                subprocess.run(["ls", str(q)])
            """,
            "tmp_path-as-arg",
            id="tmp_path_aliased_reaches_io_sink",
        ),
    ],
)
def test_r3_io_signal_detected(
    tmp_path: Path, relpath: str, body: str, expected_signal: str
) -> None:
    _write(tmp_path, relpath, body)
    finding = _first_finding(_check(tmp_path))
    assert expected_signal in finding.io_signals


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


@pytest.mark.parametrize(
    ("fixture_arg", "expected_signal"),
    [
        pytest.param(
            "tmp_path_factory", "fixture-arg:tmp_path_factory", id="io_fixture"
        ),
        pytest.param("my_pkg", "fixture-arg:my_pkg", id="suffix_match"),
    ],
)
def test_r3_fixture_io_guard_detected(
    tmp_path: Path, fixture_arg: str, expected_signal: str
) -> None:
    _write(
        tmp_path,
        "tests/unit/test_foo.py",
        f"""
        def test_x({fixture_arg}):
            assert {fixture_arg} is not None
        """,
    )
    finding = _first_finding(_check(tmp_path))
    assert expected_signal in finding.io_signals
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


def test_conftest_fixture_io_is_hard_signal_not_neutralised_by_mock(
    tmp_path: Path,
) -> None:
    """Conftest fixture I/O survives R5 mock-neutralisation (Bug 1).

    A test that mocks an in-body I/O target but consumes a fixture whose
    setup performs real ``mkdir``/``touch`` must remain ``integration``.
    The fixture I/O happens at pytest setup time, independent of any mock
    inside the test body.
    """
    _write(tmp_path, "tests/conftest.py", "")
    _write(
        tmp_path,
        "tests/unit/conftest.py",
        """
        import pytest

        @pytest.fixture
        def project_path(tmp_path):
            (tmp_path / 'src').mkdir()
            (tmp_path / 'src' / '__init__.py').touch()
            return tmp_path
        """,
    )
    _write(
        tmp_path,
        "tests/unit/test_foo.py",
        """
        from unittest.mock import MagicMock
        import pytest

        def test_x(project_path, monkeypatch):
            mock = MagicMock()
            mock.return_value.stdout = '[]'
            monkeypatch.setattr('shutil.copy', mock)
            assert mock is not None
        """,
    )
    finding = _first_finding(_check(tmp_path))
    assert finding.has_real_io is True
    assert finding.level == "integration"
    assert any(s.startswith("conftest-fixture-io:") for s in finding.io_signals)


def test_path_is_file_detected_as_io(tmp_path: Path) -> None:
    """``Path.is_file()`` triggers attr-IO signal (Bug 2).

    Stat-family attrs (``is_file``, ``exists``, ``is_dir``, ``stat``,
    ``lstat``) are real syscalls and must mark a test as ``has_real_io``.
    """
    _write(
        tmp_path,
        "tests/unit/test_foo.py",
        """
        from pathlib import Path

        DOC = Path(__file__).parent / 'somefile.md'

        def test_x():
            assert DOC.is_file()
        """,
    )
    finding = _first_finding(_check(tmp_path))
    assert finding.has_real_io is True
    assert finding.level == "integration"
    assert "attr:.is_file()" in finding.io_signals


def test_path_exists_detected_as_io(tmp_path: Path) -> None:
    """``Path.exists()`` triggers attr-IO signal (Bug 2)."""
    _write(
        tmp_path,
        "tests/unit/test_foo.py",
        """
        from pathlib import Path

        def test_x():
            assert Path('/tmp').exists()
        """,
    )
    finding = _first_finding(_check(tmp_path))
    assert finding.has_real_io is True
    assert "attr:.exists()" in finding.io_signals


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


# ---------------------------------------------------------------------------
# tmp_path false-positive regression suite (refined `_tmp_path_reaches_call`
# + structural `fixture-arg:tmp_path` suppression).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "body",
    [
        pytest.param(
            """
            import pytest

            def scaffold(path, *, workspace=False, member=None):
                raise SystemExit(1)

            def test_x(tmp_path):
                with pytest.raises(SystemExit, match="1"):
                    scaffold(str(tmp_path), workspace=True, member="foo")
            """,
            id="str_wrapper_in_pytest_raises",
        ),
        pytest.param(
            """
            from dataclasses import dataclass
            from pathlib import Path

            @dataclass
            class Cfg:
                destination: Path

            def test_x(tmp_path):
                cfg = Cfg(destination=tmp_path / "project")
                assert cfg.destination.name == "project"
            """,
            id="pydantic_constructor",
        ),
    ],
)
def test_tmp_path_attribute_only_access_is_unit(tmp_path: Path, body: str) -> None:
    """`tmp_path` only used for attribute access / non-IO ctor stays unit."""
    _write(tmp_path, "tests/unit/test_foo.py", body)
    finding = _first_finding(_check(tmp_path))
    assert finding.level == "unit"
    assert finding.has_real_io is False
    assert "tmp_path-as-arg" not in finding.io_signals
    assert "fixture-arg:tmp_path" not in finding.io_signals


def test_tmp_path_to_pydantic_validation_in_pytest_raises_is_unit(
    tmp_path: Path,
) -> None:
    """`Cfg(destination=tmp_path)` inside pytest.raises classifies as unit."""
    _write(
        tmp_path,
        "tests/unit/test_foo.py",
        """
        import pytest

        class Cfg:
            def __init__(self, *, destination, data):
                raise ValueError("missing template_path")

        def test_x(tmp_path):
            with pytest.raises(ValueError):
                Cfg(destination=tmp_path, data={})
        """,
    )
    finding = _first_finding(_check(tmp_path))
    assert finding.level == "unit"
    assert finding.has_real_io is False


def test_tmp_path_write_text_still_integration(tmp_path: Path) -> None:
    """True positive: ``tmp_path.write_text`` must remain integration."""
    _write(
        tmp_path,
        "tests/unit/test_foo.py",
        """
        def test_x(tmp_path):
            tmp_path.write_text("x")
        """,
    )
    finding = _first_finding(_check(tmp_path))
    assert finding.level == "integration"
    assert finding.has_real_io is True
    assert "tmp_path+write/read" in finding.io_signals


def test_tmp_path_to_subprocess_classifies_integration(tmp_path: Path) -> None:
    """Raw subprocess with real filesystem I/O classifies as integration."""
    _write(
        tmp_path,
        "tests/unit/test_foo.py",
        """
        import subprocess

        def test_x(tmp_path):
            subprocess.run(["ls", str(tmp_path)])
        """,
    )
    finding = _first_finding(_check(tmp_path))
    assert finding.has_subprocess is True
    assert finding.level == "integration"
    assert finding.has_real_io is True


def test_tmp_path_ctor_then_method_call_still_integration(tmp_path: Path) -> None:
    """True positive: constructor result used in method call → integration."""
    _write(
        tmp_path,
        "tests/unit/test_foo.py",
        """
        from pathlib import Path

        class Manager:
            def __init__(self, *, pypirc_path):
                self.pypirc_path = pypirc_path
            def save(self, token):
                return self.pypirc_path.write_text(token)

        def test_x(tmp_path):
            manager = Manager(pypirc_path=tmp_path / ".pypirc")
            manager.save("x")
        """,
    )
    finding = _first_finding(_check(tmp_path))
    assert finding.level == "integration"
    assert finding.has_real_io is True
    assert "fixture-arg:tmp_path" in finding.io_signals
