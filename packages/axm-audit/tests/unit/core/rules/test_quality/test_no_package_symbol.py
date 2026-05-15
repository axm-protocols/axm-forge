"""Unit tests for the TEST_QUALITY_NO_PACKAGE_SYMBOL rule.

All tests are pure in-memory: synthetic ASTs and synthetic test-file
layouts on tmp_path. No real project on disk, no subprocess.

The rule under test enforces a dual criterion on integration/e2e tests:
  (a) the test exercises a first-party Python symbol from the package, OR
  (b) the test invokes a declared `[project.scripts]` entrypoint via
      subprocess / CliRunner.

Verdicts:
  * OK                       — at least one criterion passes
  * MISLOCATED_INTEGRATION   — only (a) passes in tests/e2e/
  * NO_PACKAGE_SYMBOL        — neither (a) nor (b)
"""

from __future__ import annotations

import ast
import textwrap
from pathlib import Path

import pytest

from axm_audit.core.rules.base import Severity
from axm_audit.core.rules.test_quality._shared import (
    test_invokes_in_package_script,
    test_references_first_party,
)
from axm_audit.core.rules.test_quality.no_package_symbol import (
    NoPackageSymbolRule,
)


def _write_pkg(tmp_path: Path, *, script_name: str = "pkg-cli") -> Path:
    """Lay out a minimal package with src/pkg + tests/ + [project.scripts]."""
    pkg_root = tmp_path / "pkg-proj"
    (pkg_root / "src" / "pkg" / "core").mkdir(parents=True)
    (pkg_root / "src" / "pkg" / "__init__.py").write_text("")
    (pkg_root / "src" / "pkg" / "core" / "__init__.py").write_text("")
    (pkg_root / "src" / "pkg" / "core" / "mod.py").write_text(
        "def fn() -> int:\n    return 1\n\nclass Rule:\n    pass\n"
    )
    (pkg_root / "tests").mkdir()
    (pkg_root / "tests" / "unit").mkdir()
    (pkg_root / "tests" / "integration").mkdir()
    (pkg_root / "tests" / "e2e").mkdir()
    (pkg_root / "pyproject.toml").write_text(
        textwrap.dedent(
            f"""
            [project]
            name = "pkg"
            version = "0.0.0"

            [project.scripts]
            {script_name} = "pkg.cli:main"
            """
        ).strip()
    )
    return pkg_root


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


# ----------------------------------------------------------------------
# AC3, AC4, AC5 — verdict logic via the full rule
# ----------------------------------------------------------------------


_BODY_A_ONLY = "from pkg.core.mod import fn\n\ndef test_x():\n    assert fn() == 1\n"
_BODY_B_ONLY = (
    "import subprocess\n\n"
    "def test_x():\n"
    '    subprocess.run(["pkg-cli", "do"], check=True)\n'
)
_BODY_BOTH = (
    "import subprocess\n"
    "from pkg.core.mod import fn\n\n"
    "def test_x():\n"
    "    fn()\n"
    '    subprocess.run(["pkg-cli", "do"], check=True)\n'
)


@pytest.mark.parametrize(
    "body",
    [_BODY_A_ONLY, _BODY_B_ONLY, _BODY_BOTH],
    ids=["a-only", "b-only", "both"],
)
def test_verdict_ok_when_either_criterion_passes(tmp_path: Path, body: str) -> None:
    """AC3: at least one criterion → no finding in tests/integration/."""
    pkg_root = _write_pkg(tmp_path)
    (pkg_root / "tests" / "integration" / "test_x.py").write_text(body)
    rule = NoPackageSymbolRule()
    result = rule.check(pkg_root)
    assert result.passed is True
    assert result.details["findings"] == []


def test_verdict_mislocated_for_a_only_in_e2e_dir(tmp_path: Path) -> None:
    """AC4: (a)-pass-(b)-fail in tests/e2e/ → MISLOCATED_INTEGRATION."""
    pkg_root = _write_pkg(tmp_path)
    (pkg_root / "tests" / "e2e" / "test_x.py").write_text(
        "from pkg.core.mod import fn\n\ndef test_x():\n    assert fn() == 1\n"
    )
    rule = NoPackageSymbolRule()
    result = rule.check(pkg_root)
    assert result.passed is False
    findings = result.details["findings"]
    assert len(findings) == 1
    assert findings[0]["verdict"] == "MISLOCATED_INTEGRATION"
    assert "tests/integration/" in (result.fix_hint or "")


def test_verdict_no_symbol_when_both_fail(tmp_path: Path) -> None:
    """AC5: neither criterion in tests/integration/ → NO_PACKAGE_SYMBOL."""
    pkg_root = _write_pkg(tmp_path)
    (pkg_root / "tests" / "integration" / "test_x.py").write_text(
        "from pathlib import Path\n\n"
        "def test_x(tmp_path):\n"
        "    Path(tmp_path / 'README.md').write_text('hi')\n"
        "    assert (tmp_path / 'README.md').read_text() == 'hi'\n"
    )
    rule = NoPackageSymbolRule()
    result = rule.check(pkg_root)
    assert result.passed is False
    findings = result.details["findings"]
    assert len(findings) == 1
    assert findings[0]["verdict"] == "NO_PACKAGE_SYMBOL"
    hint = result.fix_hint or ""
    assert "versioned rule" in hint or "linter" in hint


# ----------------------------------------------------------------------
# AC6 — severity / score / payload shape
# ----------------------------------------------------------------------


def test_severity_and_score(tmp_path: Path) -> None:
    """AC6: one finding → severity=WARNING, score=98."""
    pkg_root = _write_pkg(tmp_path)
    (pkg_root / "tests" / "integration" / "test_x.py").write_text(
        "def test_x():\n    assert 1 + 1 == 2\n"
    )
    rule = NoPackageSymbolRule()
    result = rule.check(pkg_root)
    assert result.severity == Severity.WARNING
    assert result.score == 98


def test_score_floors_at_zero(tmp_path: Path) -> None:
    """AC6: score never drops below 0 even with many findings."""
    pkg_root = _write_pkg(tmp_path)
    for i in range(60):
        (pkg_root / "tests" / "integration" / f"test_x_{i}.py").write_text(
            "def test_x():\n    assert 1 + 1 == 2\n"
        )
    rule = NoPackageSymbolRule()
    result = rule.check(pkg_root)
    assert result.score == 0


def test_findings_payload_shape(tmp_path: Path) -> None:
    """AC6: every finding has the documented keys."""
    pkg_root = _write_pkg(tmp_path)
    (pkg_root / "tests" / "integration" / "test_x.py").write_text(
        "def test_x():\n    assert 1 + 1 == 2\n"
    )
    rule = NoPackageSymbolRule()
    result = rule.check(pkg_root)
    findings = result.details["findings"]
    assert len(findings) == 1
    finding = findings[0]
    for key in ("test_file", "verdict", "criterion_a_passed", "criterion_b_passed"):
        assert key in finding, f"missing key: {key}"


# ----------------------------------------------------------------------
# AC7 — opt-out markers
# ----------------------------------------------------------------------


def test_marker_no_package_symbol_ok_skips_file(tmp_path: Path) -> None:
    """AC7: file-level `pytestmark = pytest.mark.no_package_symbol_ok` skips."""
    pkg_root = _write_pkg(tmp_path)
    (pkg_root / "tests" / "integration" / "test_x.py").write_text(
        "import pytest\n"
        "pytestmark = pytest.mark.no_package_symbol_ok\n\n"
        "def test_x():\n    assert 1 + 1 == 2\n"
    )
    rule = NoPackageSymbolRule()
    result = rule.check(pkg_root)
    assert result.passed is True
    assert result.details["findings"] == []


def test_marker_no_package_symbol_ok_per_test(tmp_path: Path) -> None:
    """AC7: per-test marker excludes only the marked test."""
    pkg_root = _write_pkg(tmp_path)
    (pkg_root / "tests" / "integration" / "test_x.py").write_text(
        "import pytest\n\n"
        "@pytest.mark.no_package_symbol_ok\n"
        "def test_x():\n    assert 1 + 1 == 2\n\n"
        "def test_y():\n    assert 2 + 2 == 4\n"
    )
    rule = NoPackageSymbolRule()
    result = rule.check(pkg_root)
    findings = result.details["findings"]
    # test_x is opted out, test_y still has no symbol/script → 1 finding max.
    assert len(findings) <= 1


# ----------------------------------------------------------------------
# AC8 — unit tier is skipped
# ----------------------------------------------------------------------


def test_unit_tier_is_skipped(tmp_path: Path) -> None:
    """AC8: offenders under tests/unit/ never produce findings."""
    pkg_root = _write_pkg(tmp_path)
    (pkg_root / "tests" / "unit" / "test_x.py").write_text(
        "def test_x():\n    assert 1 + 1 == 2\n"
    )
    rule = NoPackageSymbolRule()
    result = rule.check(pkg_root)
    assert result.passed is True
    assert result.details["findings"] == []
