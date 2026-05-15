"""Unit tests for the TEST_QUALITY_NO_PACKAGE_SYMBOL rule detectors.

In-memory AST tests only. The rule's end-to-end behavior on synthetic
project layouts lives in
``tests/integration/test_no_package_symbol_rule_on_synthetic_projects.py``.

The rule under test enforces a dual criterion on integration/e2e tests:
  (a) the test exercises a first-party Python symbol from the package, OR
  (b) the test invokes a declared `[project.scripts]` entrypoint via
      subprocess / CliRunner.
"""

from __future__ import annotations

import ast
import textwrap

from axm_audit.core.rules.test_quality._shared import (
    test_invokes_in_package_script,
    test_references_first_party,
)
from axm_audit.core.rules.test_quality.no_package_symbol import (
    NoPackageSymbolRule,
)


def _parse(src: str) -> ast.Module:
    return ast.parse(textwrap.dedent(src).strip())


# ----------------------------------------------------------------------
# AC2 — rule identity
# ----------------------------------------------------------------------


def test_rule_id_constant() -> None:
    """AC2: the rule exposes a stable identifier."""
    rule = NoPackageSymbolRule()
    assert rule.rule_id == "TEST_QUALITY_NO_PACKAGE_SYMBOL"


# ----------------------------------------------------------------------
# AC3 — criterion (a): first-party symbol exercise
# ----------------------------------------------------------------------


def test_criterion_a_first_party_import() -> None:
    """AC3: direct first-party import + call returns True."""
    mod = _parse(
        """
        from pkg.core.mod import fn

        def test_x():
            assert fn() == 1
        """
    )
    test_func = next(
        n for n in mod.body if isinstance(n, ast.FunctionDef) and n.name == "test_x"
    )
    assert (
        test_references_first_party(
            test_func=test_func,
            module_ast=mod,
            pkg_prefixes={"pkg"},
        )
        is True
    )


def test_criterion_a_via_fixture_return_annotation() -> None:
    """AC3: fixture whose return annotation is first-party is enough."""
    mod = _parse(
        """
        import pytest
        from pkg.core.mod import Rule

        @pytest.fixture
        def my_rule() -> Rule:
            return None  # body lies; annotation is the contract

        def test_x(my_rule):
            assert my_rule is not None
        """
    )
    test_func = next(
        n for n in mod.body if isinstance(n, ast.FunctionDef) and n.name == "test_x"
    )
    assert (
        test_references_first_party(
            test_func=test_func,
            module_ast=mod,
            pkg_prefixes={"pkg"},
        )
        is True
    )


def test_criterion_a_via_fixture_return_body() -> None:
    """AC3: fixture body `return Rule(...)` resolves first-party."""
    mod = _parse(
        """
        import pytest
        from pkg.core.mod import Rule

        @pytest.fixture
        def my_rule():
            return Rule()

        def test_x(my_rule):
            assert my_rule is not None
        """
    )
    test_func = next(
        n for n in mod.body if isinstance(n, ast.FunctionDef) and n.name == "test_x"
    )
    assert (
        test_references_first_party(
            test_func=test_func,
            module_ast=mod,
            pkg_prefixes={"pkg"},
        )
        is True
    )


def test_criterion_a_via_module_helper_closure() -> None:
    """AC3: helper at module scope using first-party symbol is in closure."""
    mod = _parse(
        """
        from pkg.core.mod import fn

        def _make_value():
            return fn()

        def test_x():
            assert _make_value() == 1
        """
    )
    test_func = next(
        n for n in mod.body if isinstance(n, ast.FunctionDef) and n.name == "test_x"
    )
    assert (
        test_references_first_party(
            test_func=test_func,
            module_ast=mod,
            pkg_prefixes={"pkg"},
        )
        is True
    )


def test_criterion_a_no_first_party_import() -> None:
    """AC3: only stdlib imports → no first-party reference."""
    mod = _parse(
        """
        import json
        from pathlib import Path

        def test_x():
            assert json.dumps({"a": 1}) == '{"a": 1}'
        """
    )
    test_func = next(
        n for n in mod.body if isinstance(n, ast.FunctionDef) and n.name == "test_x"
    )
    assert (
        test_references_first_party(
            test_func=test_func,
            module_ast=mod,
            pkg_prefixes={"pkg"},
        )
        is False
    )


# ----------------------------------------------------------------------
# AC3 — criterion (b): in-package script invocation
# ----------------------------------------------------------------------


def test_criterion_b_subprocess_with_declared_script() -> None:
    """AC3: `subprocess.run(["pkg-cli", "do"])` invokes a declared script."""
    mod = _parse(
        """
        import subprocess

        def test_x():
            subprocess.run(["pkg-cli", "do"], check=True)
        """
    )
    test_func = next(
        n for n in mod.body if isinstance(n, ast.FunctionDef) and n.name == "test_x"
    )
    assert (
        test_invokes_in_package_script(
            test_func=test_func,
            module_ast=mod,
            project_scripts={"pkg-cli"},
        )
        is True
    )


def test_criterion_b_subprocess_with_module_path_form() -> None:
    """AC3: `python -m <pkg_module>` matches the script's module alias.

    The alias for a hyphenated script ``pkg-cli`` is ``pkg_cli`` — the
    module-path form must use the underscore alias to match.
    """
    mod = _parse(
        """
        import subprocess
        import sys

        def test_x():
            subprocess.run([sys.executable, "-m", "pkg_cli", "do"], check=True)
        """
    )
    test_func = next(
        n for n in mod.body if isinstance(n, ast.FunctionDef) and n.name == "test_x"
    )
    assert (
        test_invokes_in_package_script(
            test_func=test_func,
            module_ast=mod,
            project_scripts={"pkg-cli"},
        )
        is True
    )


def test_criterion_b_subprocess_plumbing_only() -> None:
    """AC3: plumbing subprocess calls (git, uv) do NOT satisfy (b)."""
    mod = _parse(
        """
        import subprocess

        def test_x(tmp_path):
            subprocess.run(["git", "init"], cwd=tmp_path, check=True)
            subprocess.run(["uv", "venv"], cwd=tmp_path, check=True)
        """
    )
    test_func = next(
        n for n in mod.body if isinstance(n, ast.FunctionDef) and n.name == "test_x"
    )
    assert (
        test_invokes_in_package_script(
            test_func=test_func,
            module_ast=mod,
            project_scripts={"pkg-cli"},
        )
        is False
    )


def test_criterion_b_clirunner_invoke_single_binary() -> None:
    """AC3: `CliRunner().invoke(app, [...])` is recognised for single-script pkgs."""
    mod = _parse(
        """
        from click.testing import CliRunner
        from pkg.cli import app

        def test_x():
            runner = CliRunner()
            result = runner.invoke(app, ["do"])
            assert result.exit_code == 0
        """
    )
    test_func = next(
        n for n in mod.body if isinstance(n, ast.FunctionDef) and n.name == "test_x"
    )
    assert (
        test_invokes_in_package_script(
            test_func=test_func,
            module_ast=mod,
            project_scripts={"pkg-cli"},
        )
        is True
    )


def test_criterion_b_unresolved_argv_skipped() -> None:
    """AC3: argv with one unresolved element (e.g. str(tmp_path)) is permissive."""
    mod = _parse(
        """
        import subprocess

        def test_x(tmp_path):
            subprocess.run(["pkg-cli", "audit", str(tmp_path)], check=True)
        """
    )
    test_func = next(
        n for n in mod.body if isinstance(n, ast.FunctionDef) and n.name == "test_x"
    )
    assert (
        test_invokes_in_package_script(
            test_func=test_func,
            module_ast=mod,
            project_scripts={"pkg-cli"},
        )
        is True
    )
