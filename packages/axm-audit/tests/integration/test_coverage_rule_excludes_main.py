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
