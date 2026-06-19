"""Integration test: TestCoverageRule omits __main__.py from gap list (AXM-1663)."""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from axm_audit.core.rules.coverage import TestCoverageRule


@pytest.mark.integration
def test_coverage_rule_omits_main_in_gap_list(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    src_pkg = project / "src" / "mypkg"
    src_pkg.mkdir(parents=True)
    (src_pkg / "__init__.py").write_text("def add(a, b):\n    return a + b\n")
    (src_pkg / "__main__.py").write_text(
        "from . import add\n\nif __name__ == '__main__':\n    print(add(1, 2))\n"
    )

    tests_dir = project / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_add.py").write_text(
        "from mypkg import add\n\ndef test_add():\n    assert add(1, 2) == 3\n"
    )

    (project / "pyproject.toml").write_text(
        textwrap.dedent(
            """
            [build-system]
            requires = ["hatchling"]
            build-backend = "hatchling.build"

            [project]
            name = "mypkg"
            version = "0.0.1"
            requires-python = ">=3.12"

            [tool.hatch.build.targets.wheel]
            packages = ["src/mypkg"]

            [tool.pytest.ini_options]
            pythonpath = ["src"]
            testpaths = ["tests"]
            """
        ).strip()
        + "\n"
    )

    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", ".", "--quiet"],
        cwd=project,
        check=False,
    )

    rule = TestCoverageRule()
    result = rule.check(project)

    assert "__main__.py" not in (result.text or "")


def _make_low_coverage_project(tmp_path: Path, coverage_section: str) -> Path:
    """Materialize a demo package on disk that reports ~33% coverage.

    Only ``covered`` is exercised by the test; ``uncovered_a``/``uncovered_b``
    are never called, so coverage lands well below the default 90 threshold.
    """
    project = tmp_path / "proj"
    src_pkg = project / "src" / "lowcov"
    src_pkg.mkdir(parents=True)
    (src_pkg / "__init__.py").write_text(
        textwrap.dedent(
            """
            def covered():
                return 1

            def uncovered_a():
                x = 2
                y = 3
                return x + y

            def uncovered_b():
                a = 4
                b = 5
                return a + b
            """
        ).strip()
        + "\n"
    )

    tests_dir = project / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_covered.py").write_text(
        "from lowcov import covered\n\ndef test_covered():\n    assert covered() == 1\n"
    )

    (project / "pyproject.toml").write_text(
        textwrap.dedent(
            """
            [build-system]
            requires = ["hatchling"]
            build-backend = "hatchling.build"

            [project]
            name = "lowcov"
            version = "0.0.1"
            requires-python = ">=3.12"

            [tool.hatch.build.targets.wheel]
            packages = ["src/lowcov"]

            [tool.pytest.ini_options]
            pythonpath = ["src"]
            testpaths = ["tests"]
            """
        ).strip()
        + "\n"
        + coverage_section
    )

    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", ".", "--quiet"],
        cwd=project,
        check=False,
    )
    return project


@pytest.mark.integration
@pytest.mark.parametrize(
    ("coverage_section", "expected_passed"),
    [
        pytest.param(
            "\n[tool.axm-audit.coverage]\nmin_coverage = 0\n",
            True,
            id="configured_zero_threshold_passes",
        ),
        pytest.param("", False, id="default_threshold_fails_low_coverage"),
    ],
)
def test_check_honors_configured_threshold(
    tmp_path: Path, coverage_section: str, expected_passed: bool
) -> None:
    """AC4/AC5: the configured min_coverage governs the gate on a low-cov project.

    With ``min_coverage = 0`` the same low-coverage project passes; without any
    config it fails against the default 90.
    """
    project = _make_low_coverage_project(tmp_path, coverage_section)

    result = TestCoverageRule().check(project)

    assert result.passed is expected_passed
