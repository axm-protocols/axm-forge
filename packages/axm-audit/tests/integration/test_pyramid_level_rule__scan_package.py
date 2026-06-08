from __future__ import annotations

import ast
import textwrap
from pathlib import Path
from textwrap import dedent

import pytest

from axm_audit.core.rules.test_quality.pyramid_level import (
    PyramidLevelRule,
    scan_package,
    scan_test_file,
)

pytestmark = pytest.mark.integration


def _make_pkg(root: Path) -> Path:
    pkg = root / "pkg"
    src = pkg / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "core.py").write_text("def add(a, b):\n    return a + b\n")
    (pkg / "tests").mkdir()
    (pkg / "tests" / "__init__.py").write_text("")
    return pkg


def test_findings_unchanged_after_render_change(tmp_path: Path) -> None:
    """AC4: scan_package yields the same finding set (presentation-only change).

    A unit-located test that performs real filesystem I/O must be flagged as
    a unit->integration mismatch. The rendering change must not alter the set
    of findings (paths/levels) produced.
    """
    pkg = _make_pkg(tmp_path)
    unit_dir = pkg / "tests" / "unit"
    unit_dir.mkdir(parents=True)
    (unit_dir / "__init__.py").write_text("")
    (unit_dir / "test_io.py").write_text(
        "def test_writes(tmp_path):\n"
        "    (tmp_path / 'f.txt').write_text('x')\n"
        "    assert (tmp_path / 'f.txt').read_text() == 'x'\n"
    )

    findings = scan_package(pkg)

    located = [
        (Path(f.path).name, f.current_level, f.level)
        for f in findings
        if Path(f.path).name == "test_io.py"
    ]
    assert located == [("test_io.py", "unit", "integration")]


def test_pyramid_level_fails_when_root_tests_with_pyramid_subdirs(
    tmp_path: Path,
) -> None:
    pkg = _make_pkg(tmp_path)
    (pkg / "tests" / "test_foo.py").write_text(
        "from pkg.core import add\n\ndef test_add():\n    assert add(1, 2) == 3\n"
    )
    (pkg / "tests" / "unit").mkdir()
    (pkg / "tests" / "unit" / "__init__.py").write_text("")

    result = PyramidLevelRule().check(pkg)

    assert result.passed is False
    details = result.details
    assert details is not None
    assert details["total"] == 1
    mismatches = details["mismatches"]
    assert len(mismatches) == 1
    entry = mismatches[0]
    assert entry["current_level"] == "root"
    assert entry["level"] == "unit"


def test_pyramid_level_passes_when_no_pyramid_subdirs(tmp_path: Path) -> None:
    pkg = _make_pkg(tmp_path)
    (pkg / "tests" / "test_foo.py").write_text(
        "from pkg.core import add\n\ndef test_add():\n    assert add(1, 2) == 3\n"
    )

    result = PyramidLevelRule().check(pkg)

    assert result.passed is True
    details = result.details
    assert details is not None
    assert details["total"] == 0


def test_pyramid_level_mixed_root_and_subdir_tests(tmp_path: Path) -> None:
    pkg = _make_pkg(tmp_path)
    (pkg / "tests" / "test_foo.py").write_text(
        "from pkg.core import add\n\ndef test_add():\n    assert add(1, 2) == 3\n"
    )
    unit_dir = pkg / "tests" / "unit"
    unit_dir.mkdir()
    (unit_dir / "__init__.py").write_text("")
    (unit_dir / "test_bar.py").write_text(
        "from pkg.core import add\n\ndef test_bar():\n    assert add(2, 3) == 5\n"
    )
    integ_dir = pkg / "tests" / "integration"
    integ_dir.mkdir()
    (integ_dir / "__init__.py").write_text("")

    result = PyramidLevelRule().check(pkg)

    assert result.passed is False
    details = result.details
    assert details is not None
    mismatches = details["mismatches"]
    assert len(mismatches) == 1
    assert mismatches[0]["path"].endswith("tests/test_foo.py")


def test_pyramid_level_root_test_classified_as_integration(tmp_path: Path) -> None:
    pkg = _make_pkg(tmp_path)
    (pkg / "tests" / "test_io.py").write_text(
        "from pathlib import Path\n"
        "from pkg.core import add\n\n"
        "def test_io(tmp_path):\n"
        "    p = tmp_path / 'x.txt'\n"
        "    p.write_text('hello')\n"
        "    assert p.read_text() == 'hello'\n"
        "    assert add(1, 1) == 2\n"
    )
    integ_dir = pkg / "tests" / "integration"
    integ_dir.mkdir()
    (integ_dir / "__init__.py").write_text("")

    result = PyramidLevelRule().check(pkg)

    assert result.passed is False
    details = result.details
    assert details is not None
    mismatches = details["mismatches"]
    assert len(mismatches) == 1
    entry = mismatches[0]
    assert entry["level"] == "integration"
    assert entry["suggested_file"].startswith("integration/")


def _write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(body).lstrip())


@pytest.fixture
def pyramid_mismatch_project(tmp_path: Path) -> Path:
    _write(
        tmp_path / "tests" / "integration" / "test_x.py",
        """
        def test_pure():
            assert 1 + 1 == 2
        """,
    )
    return tmp_path


def test_pyramid_failed_populates_actionable_fields(
    pyramid_mismatch_project: Path,
) -> None:
    result = PyramidLevelRule().check(pyramid_mismatch_project)
    assert result.passed is False
    assert result.text and "•" in result.text
    assert result.fix_hint and "pyramid-relocate" in result.fix_hint
    assert result.details is not None
    assert "mismatches" in result.details
    assert result.details["total"] >= 1


def test_pyramid_passed_omits_text_and_fix_hint(tmp_path: Path) -> None:
    (tmp_path / "tests").mkdir()
    result = PyramidLevelRule().check(tmp_path)
    assert result.passed is True
    assert result.text is None
    assert result.fix_hint is None


def test_empty_tests_returns_pass(tmp_path: Path) -> None:
    result = PyramidLevelRule().check(tmp_path)
    assert result.passed is True
    assert result.score == 100
    assert list(result.findings) == []


def test_parametrized_path_arg_no_mismatch(tmp_path: Path) -> None:
    """AC4, AC5: a real unit test file using the ``axm-bib`` repro pattern
    (``@parametrize("pdf_path", ...)``) yields zero pyramid mismatches."""
    pkg = _make_pkg(tmp_path)
    unit_dir = pkg / "tests" / "unit"
    unit_dir.mkdir()
    (unit_dir / "__init__.py").write_text("")
    _write(
        unit_dir / "test_blank.py",
        """
        import pytest

        @pytest.mark.parametrize("pdf_path", ["", "   "])
        def test_blank_pdf_path_rejected(pdf_path):
            assert pdf_path.strip() == ""
        """,
    )

    result = PyramidLevelRule().check(pkg)

    assert result.passed is True
    assert result.details is not None
    assert result.details["total"] == 0


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
