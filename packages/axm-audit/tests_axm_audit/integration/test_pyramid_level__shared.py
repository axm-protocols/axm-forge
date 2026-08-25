"""Pyramid classifier credits inline ``python -c \"<first-party>\"`` as e2e.

Regression guard for the blind spot shared with
``TEST_QUALITY_NO_PACKAGE_SYMBOL``: a black-box e2e test that drives the
package via ``subprocess.run([sys.executable, \"-c\", script, ...])`` where the
inline ``script`` imports a first-party package must classify as ``e2e``, not
``integration`` -- even when the package declares no ``[project.scripts]``.
"""

from __future__ import annotations

import ast
import textwrap
from pathlib import Path

import pytest

from axm_audit.core.fix.findings import func_canonical
from axm_audit.core.rules.test_quality._shared import load_project_scripts
from axm_audit.core.rules.test_quality.pyramid_level import scan_test_file

pytestmark = pytest.mark.integration


def _scan_one(tmp_path: Path, src: str, pkg_prefixes: set[str]) -> object:
    """Write *src* into a scriptless package and classify its single test."""
    pkg_root = tmp_path
    tests_dir = pkg_root / "tests" / "e2e"
    tests_dir.mkdir(parents=True)
    test_file = tests_dir / "test_overfit.py"
    test_file.write_text(textwrap.dedent(src).lstrip())
    tree = ast.parse(test_file.read_text())
    findings = scan_test_file(test_file, tree, pkg_root, pkg_prefixes, None, tests_dir)
    assert len(findings) == 1
    return findings[0]


def test_inline_python_c_first_party_classifies_e2e(tmp_path: Path) -> None:
    """Inline ``python -c`` importing a first-party pkg -> e2e (no scripts)."""
    src = """
        import subprocess
        import sys
        import textwrap

        import pytest

        pytestmark = [pytest.mark.e2e]

        def test_x(tmp_path):
            script = textwrap.dedent('''
                from axm_train.core.lora import train_lora
                train_lora()
            ''')
            subprocess.run([sys.executable, "-c", script, str(tmp_path)], check=False)
    """
    finding = _scan_one(tmp_path, src, {"axm_train"})
    assert finding.level == "e2e"
    assert finding.has_subprocess is True
    assert "subprocess" in finding.reason


def test_inline_python_c_no_first_party_not_promoted(tmp_path: Path) -> None:
    """Inline ``python -c`` importing nothing first-party stays non-e2e."""
    src = """
        import subprocess
        import sys
        import textwrap

        import pytest

        pytestmark = [pytest.mark.e2e]

        def test_x(tmp_path):
            script = textwrap.dedent('''
                import json
                print(json.dumps({}))
            ''')
            subprocess.run([sys.executable, "-c", script, str(tmp_path)], check=False)
    """
    finding = _scan_one(tmp_path, src, {"axm_train"})
    assert finding.level != "e2e"


# AC1 / AC2 - axm.tools-only packages: their CLI subprocess tests are e2e
# ---------------------------------------------------------------------

AXM_TOOLS_PYPROJECT = """\
[project]
name = "toolsonly"
version = "0.0.0"
requires-python = ">=3.12"

[project.entry-points."axm.tools"]
demo = "toolsonly.tools:DemoTool"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
"""

BARE_PYPROJECT = """\
[project]
name = "bare"
version = "0.0.0"
requires-python = ">=3.12"
"""

FIRST_ARG_CLI_TEST = """\
import subprocess


def test_cli_runs(tmp_path):
    result = subprocess.run(
        ["axm", "audit", str(tmp_path)], capture_output=True, check=False
    )
    assert result.returncode in (0, 1)
"""

MODULE_FORM_CLI_TEST = """\
import subprocess
import sys


def test_cli_runs(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "axm", "audit", str(tmp_path)],
        capture_output=True,
        check=False,
    )
    assert result.returncode in (0, 1)
"""

FOREIGN_MODULE_TEST = """\
import subprocess
import sys


def test_cli_runs(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--version"],
        capture_output=True,
        check=False,
    )
    assert result.returncode in (0, 1)
"""


def _make_cli_package(
    root: Path, pyproject: str, name: str, body: str
) -> tuple[Path, Path]:
    """Write a real package whose ``tests/e2e`` module drives the CLI."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "pyproject.toml").write_text(pyproject)
    src = root / "src" / name
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "tools.py").write_text("class DemoTool:\n    pass\n")
    tests_dir = root / "tests"
    e2e_dir = tests_dir / "e2e"
    e2e_dir.mkdir(parents=True)
    test_file = e2e_dir / "test_cli.py"
    test_file.write_text(body)
    return test_file, tests_dir


def _classify_cli_test(root: Path, pyproject: str, name: str, body: str) -> object:
    """Classify the single CLI test of a freshly written package."""
    test_file, tests_dir = _make_cli_package(root, pyproject, name, body)
    tree = ast.parse(test_file.read_text())
    findings = scan_test_file(test_file, tree, root, {name}, None, tests_dir)
    assert len(findings) == 1
    return findings[0]


def test_axm_tools_only_cli_subprocess_classifies_e2e(tmp_path: Path) -> None:
    """AC1: a subprocess CLI test of an axm.tools-only package is e2e."""
    pkg = tmp_path / "toolsonly"
    finding = _classify_cli_test(
        pkg, AXM_TOOLS_PYPROJECT, "toolsonly", FIRST_ARG_CLI_TEST
    )

    assert finding.level == "e2e", finding.reason

    # Secondary guard: load_project_scripts stays narrow (no widening).
    assert load_project_scripts(pkg) == set()
    # Secondary guard: neither table declared -> still no e2e classification.
    bare = _classify_cli_test(
        tmp_path / "bare", BARE_PYPROJECT, "bare", FIRST_ARG_CLI_TEST
    )
    assert bare.level != "e2e"


def test_axm_tools_only_module_form_classifies_e2e(tmp_path: Path) -> None:
    """AC2: ``[sys.executable, "-m", "axm", ...]`` is an in-package CLI call."""
    finding = _classify_cli_test(
        tmp_path / "toolsonly",
        AXM_TOOLS_PYPROJECT,
        "toolsonly",
        MODULE_FORM_CLI_TEST,
    )

    assert finding.level == "e2e", finding.reason

    # Secondary guard: a foreign ``-m`` module is never credited as the CLI.
    foreign = _classify_cli_test(
        tmp_path / "foreign",
        AXM_TOOLS_PYPROJECT,
        "foreign",
        FOREIGN_MODULE_TEST,
    )
    assert foreign.level != "e2e"


def test_axm_tools_only_e2e_keeps_canonical_name(tmp_path: Path) -> None:
    """AC1: the e2e promotion leaves the canonical filename untouched."""
    pkg = tmp_path / "toolsonly"
    test_file, tests_dir = _make_cli_package(
        pkg, AXM_TOOLS_PYPROJECT, "toolsonly", FIRST_ARG_CLI_TEST
    )
    tree = ast.parse(test_file.read_text())
    findings = scan_test_file(test_file, tree, pkg, {"toolsonly"}, None, tests_dir)
    assert len(findings) == 1
    assert findings[0].level == "e2e", findings[0].reason

    func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
    canonical = func_canonical(
        func,
        tree,
        tier="e2e",
        pkg_prefixes={"toolsonly"},
        scripts=load_project_scripts(pkg),
        single_binary=None,
    )
    baseline = func_canonical(
        func,
        tree,
        tier="e2e",
        pkg_prefixes={"toolsonly"},
        scripts=set(),
        single_binary=None,
    )
    # Secondary guard: the name derived from load_project_scripts is the same
    # as the no-script baseline -> the canonical naming did not move.
    assert canonical == baseline
