from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from axm_audit.core.rules.test_quality.pyramid_level import PyramidLevelRule

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
