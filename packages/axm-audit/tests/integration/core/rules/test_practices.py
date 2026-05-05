"""Tests for Practice Rules — RED phase."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

from axm_audit.models.results import Severity


class TestDocstringCoverageRuleIntegration:
    """Tests for DocstringCoverageRule (real I/O)."""

    def test_fully_documented_passes(self, tmp_path: Path) -> None:
        """All public functions with docstrings should pass."""
        from axm_audit.core.rules.practices.docstring_coverage import (
            DocstringCoverageRule,
        )

        src = tmp_path / "src"
        src.mkdir()
        (src / "documented.py").write_text('''
def public_func() -> None:
    """This function has a docstring."""
    pass

def another_public() -> str:
    """This one too."""
    return "hello"
''')

        rule = DocstringCoverageRule()
        result = rule.check(tmp_path)
        assert result.passed is True
        assert result.details is not None
        assert result.details["coverage"] >= 0.80

    def test_missing_docstrings_fails(self, tmp_path: Path) -> None:
        """Functions without docstrings should reduce coverage."""
        from axm_audit.core.rules.practices.docstring_coverage import (
            DocstringCoverageRule,
        )

        src = tmp_path / "src"
        src.mkdir()
        (src / "undocumented.py").write_text('''
def func_one() -> None:
    pass

def func_two() -> None:
    pass

def func_three() -> None:
    pass

def func_four() -> None:
    """Only this one has a docstring."""
    pass
''')

        rule = DocstringCoverageRule()
        result = rule.check(tmp_path)
        assert result.passed is False
        assert result.details is not None
        assert result.details["coverage"] < 0.80

    def test_private_functions_ignored(self, tmp_path: Path) -> None:
        """Private functions (starting with _) should not count."""
        from axm_audit.core.rules.practices.docstring_coverage import (
            DocstringCoverageRule,
        )

        src = tmp_path / "src"
        src.mkdir()
        (src / "private.py").write_text('''
def public_func() -> None:
    """Documented public function."""
    pass

def _private_helper() -> None:
    # No docstring but should be ignored
    pass
''')

        rule = DocstringCoverageRule()
        result = rule.check(tmp_path)
        assert result.passed is True


class TestBareExceptRuleIntegration:
    """Tests for BareExceptRule (real I/O)."""

    def test_typed_except_passes(self, tmp_path: Path) -> None:
        """Typed except clauses should pass."""
        from axm_audit.core.rules.practices.bare_except import BareExceptRule

        src = tmp_path / "src"
        src.mkdir()
        (src / "good.py").write_text("""
try:
    x = 1 / 0
except ZeroDivisionError:
    pass
except (ValueError, TypeError) as e:
    print(e)
""")

        rule = BareExceptRule()
        result = rule.check(tmp_path)
        assert result.passed is True

    def test_bare_except_fails(self, tmp_path: Path) -> None:
        """Bare except: should fail."""
        from axm_audit.core.rules.practices.bare_except import BareExceptRule

        src = tmp_path / "src"
        src.mkdir()
        (src / "bad.py").write_text("""
try:
    risky_operation()
except:
    pass  # Bare except!
""")

        rule = BareExceptRule()
        result = rule.check(tmp_path)
        assert result.passed is False
        assert result.details is not None
        assert result.details["bare_except_count"] > 0

    def test_find_bare_excepts_helper(self, tmp_path: Path) -> None:
        """Tests that _find_bare_excepts correctly extracts locations."""
        import ast

        from axm_audit.core.rules.practices.bare_except import BareExceptRule

        src_path = tmp_path / "src"
        src_path.mkdir()

        file_path = src_path / "bad.py"
        file_path.write_text("""
try:
    risky_operation()
except:
    pass  # Bare except!
""")

        tree = ast.parse(file_path.read_text())
        rule = BareExceptRule()
        bare_excepts: list[dict[str, str | int]] = []
        rule._find_bare_excepts(tree, file_path, src_path, bare_excepts)

        assert len(bare_excepts) == 1
        assert bare_excepts[0]["file"] == "bad.py"
        assert bare_excepts[0]["line"] == 4


class TestSecurityPatternRuleIntegration:
    """Tests for SecurityPatternRule (real I/O)."""

    def test_no_secrets_passes(self, tmp_path: Path) -> None:
        """Code without hardcoded secrets should pass."""
        from axm_audit.core.rules.security import SecurityPatternRule

        src = tmp_path / "src"
        src.mkdir()
        (src / "clean.py").write_text("""
import os

password = os.environ.get("PASSWORD")
api_key = os.getenv("API_KEY")
""")

        rule = SecurityPatternRule()
        result = rule.check(tmp_path)
        assert result.passed is True

    def test_hardcoded_password_fails(self, tmp_path: Path) -> None:
        """Hardcoded password should fail."""
        from axm_audit.core.rules.security import SecurityPatternRule

        src = tmp_path / "src"
        src.mkdir()
        (src / "bad.py").write_text("""
password = "super_secret_123"
api_key = "sk-1234567890"
""")

        rule = SecurityPatternRule()
        result = rule.check(tmp_path)
        assert result.passed is False
        assert result.details is not None
        assert result.details["secret_count"] > 0


# ─── BlockingIORule ──────────────────────────────────────────────────────────


class TestBlockingIORuleIntegration:
    """Tests for BlockingIORule (real I/O)."""

    def test_pass_no_blocking(self, tmp_path: Path) -> None:
        """Module with async def using asyncio.sleep should pass."""
        from axm_audit.core.rules.practices.blocking_io import BlockingIORule

        src = tmp_path / "src"
        src.mkdir()
        (src / "ok.py").write_text("""\
import asyncio

async def f():
    await asyncio.sleep(1)
""")

        rule = BlockingIORule()
        result = rule.check(tmp_path)
        assert result.passed is True

    def test_fail_sleep_in_async(self, tmp_path: Path) -> None:
        """time.sleep inside async def should fail."""
        from axm_audit.core.rules.practices.blocking_io import BlockingIORule

        src = tmp_path / "src"
        src.mkdir()
        (src / "bad.py").write_text("""\
import time

async def handler():
    time.sleep(1)
""")

        rule = BlockingIORule()
        result = rule.check(tmp_path)
        assert result.passed is False
        assert result.details is not None
        violations = result.details["violations"]
        assert len(violations) == 1
        assert violations[0]["issue"] == "time.sleep in async"

    def test_fail_no_timeout(self, tmp_path: Path) -> None:
        """requests.get without timeout should fail."""
        from axm_audit.core.rules.practices.blocking_io import BlockingIORule

        src = tmp_path / "src"
        src.mkdir()
        (src / "bad.py").write_text("""\
import requests

def fetch():
    requests.get("https://example.com")
""")

        rule = BlockingIORule()
        result = rule.check(tmp_path)
        assert result.passed is False
        assert result.details is not None
        violations = result.details["violations"]
        assert len(violations) == 1
        assert violations[0]["issue"] == "HTTP call without timeout"

    def test_pass_with_timeout(self, tmp_path: Path) -> None:
        """requests.get with timeout should pass."""
        from axm_audit.core.rules.practices.blocking_io import BlockingIORule

        src = tmp_path / "src"
        src.mkdir()
        (src / "ok.py").write_text("""\
import requests

def fetch():
    requests.get("https://example.com", timeout=30)
""")

        rule = BlockingIORule()
        result = rule.check(tmp_path)
        assert result.passed is True

    def test_httpx_async_client_no_timeout(self, tmp_path: Path) -> None:
        """httpx.AsyncClient().get() without timeout should fail."""
        from axm_audit.core.rules.practices.blocking_io import BlockingIORule

        src = tmp_path / "src"
        src.mkdir()
        (src / "bad.py").write_text("""\
import httpx

async def fetch():
    httpx.AsyncClient().get("https://example.com")
""")

        rule = BlockingIORule()
        result = rule.check(tmp_path)
        assert result.passed is False
        assert result.details is not None
        assert len(result.details["violations"]) >= 1


# ─── Docstring detail coverage ───────────────────────────────────────────────


class TestDocstringMissingDetail:
    """Tests for missing docstring listing (no cap, all items shown)."""

    def test_missing_no_cap(self, tmp_path: Path) -> None:
        """All missing docstrings are returned, not capped at 10."""
        from axm_audit.core.rules.practices.docstring_coverage import (
            DocstringCoverageRule,
        )

        src = tmp_path / "src"
        src.mkdir()
        # 15 undocumented + 1 documented = 6.25% coverage → fails
        funcs = "\n".join(f"def func_{i}() -> None:\n    pass\n" for i in range(15))
        funcs += '\ndef documented() -> None:\n    """Has a docstring."""\n    pass\n'
        (src / "many.py").write_text(funcs)

        rule = DocstringCoverageRule()
        result = rule.check(tmp_path)
        assert result.details is not None
        assert len(result.details["missing"]) == 15

    def test_missing_list_contains_locations(self, tmp_path: Path) -> None:
        """Each missing entry has file:function format."""
        from axm_audit.core.rules.practices.docstring_coverage import (
            DocstringCoverageRule,
        )

        src = tmp_path / "src"
        src.mkdir()
        (src / "mod.py").write_text("def foo() -> None:\n    pass\n")

        rule = DocstringCoverageRule()
        result = rule.check(tmp_path)
        assert result.details is not None
        assert any("foo" in m for m in result.details["missing"])

    def test_fully_documented_empty_missing(self, tmp_path: Path) -> None:
        """100% coverage returns empty missing list."""
        from axm_audit.core.rules.practices.docstring_coverage import (
            DocstringCoverageRule,
        )

        src = tmp_path / "src"
        src.mkdir()
        (src / "ok.py").write_text('def ok() -> None:\n    """Ok."""\n    pass\n')

        rule = DocstringCoverageRule()
        result = rule.check(tmp_path)
        assert result.details is not None
        assert result.details["missing"] == []


# ─── MirrorRule ──────────────────────────────────────────────────────────


class TestMirrorRuleIntegration:
    """Tests for MirrorRule — 1:1 source-to-test file mapping (real I/O)."""

    def test_pass_all_modules_tested(self, tmp_path: Path) -> None:
        """All source modules with matching test files should pass."""
        from axm_audit.core.rules.practices.mirror import MirrorRule

        pkg = tmp_path / "src" / "pkg"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("")
        (pkg / "a.py").write_text("def hello(): pass\n")
        (pkg / "b.py").write_text("def world(): pass\n")

        tests = tmp_path / "tests"
        tests.mkdir()
        (tests / "test_a.py").write_text("def test_a(): pass\n")
        (tests / "test_b.py").write_text("def test_b(): pass\n")

        rule = MirrorRule()
        result = rule.check(tmp_path)
        assert result.passed is True
        assert result.fix_hint is None

    def test_fail_missing_tests(self, tmp_path: Path) -> None:
        """Missing test file should fail with details listing the module."""
        from axm_audit.core.rules.practices.mirror import MirrorRule

        pkg = tmp_path / "src" / "pkg"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("")
        (pkg / "a.py").write_text("def hello(): pass\n")
        (pkg / "b.py").write_text("def world(): pass\n")

        tests = tmp_path / "tests"
        tests.mkdir()
        (tests / "test_a.py").write_text("def test_a(): pass\n")
        # No test_b.py!

        rule = MirrorRule()
        result = rule.check(tmp_path)
        assert result.passed is False
        assert result.details is not None
        assert "b.py" in result.details["missing"]
        assert result.fix_hint is not None
        assert "test_b.py" in result.fix_hint

    def test_exempt_init_main_and_version(self, tmp_path: Path) -> None:
        """__init__/__main__/_version are exempt from test requirement."""
        from axm_audit.core.rules.practices.mirror import MirrorRule

        pkg = tmp_path / "src" / "pkg"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("")
        (pkg / "__main__.py").write_text("print('hi')\n")
        (pkg / "_version.py").write_text("__version__ = '0.1'\n")
        (pkg / "a.py").write_text("def hello(): pass\n")

        tests = tmp_path / "tests"
        tests.mkdir()
        (tests / "test_a.py").write_text("def test_a(): pass\n")

        rule = MirrorRule()
        result = rule.check(tmp_path)
        assert result.passed is True
        assert result.details is not None
        assert result.details["missing"] == []

    def test_nested_test_dirs(self, tmp_path: Path) -> None:
        """Test files in nested directories (tests/core/) should match."""
        from axm_audit.core.rules.practices.mirror import MirrorRule

        pkg = tmp_path / "src" / "pkg"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("")
        (pkg / "foo.py").write_text("def foo(): pass\n")

        tests = tmp_path / "tests" / "core"
        tests.mkdir(parents=True)
        (tests / "test_foo.py").write_text("def test_foo(): pass\n")

        rule = MirrorRule()
        result = rule.check(tmp_path)
        assert result.passed is True

    def test_no_src_directory(self, tmp_path: Path) -> None:
        """Empty project without src/ should pass with INFO."""
        from axm_audit.core.rules.practices.mirror import MirrorRule

        rule = MirrorRule()
        result = rule.check(tmp_path)
        assert result.passed is True
        assert result.severity == Severity.INFO

    def test_empty_src_only_init(self, tmp_path: Path) -> None:
        """Package with only __init__.py should pass (all exempt)."""
        from axm_audit.core.rules.practices.mirror import MirrorRule

        pkg = tmp_path / "src" / "pkg"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("")

        rule = MirrorRule()
        result = rule.check(tmp_path)
        assert result.passed is True

    # --- AXM-857: private module underscore stripping ---

    def test_private_module_matches_stripped_test(self, tmp_path: Path) -> None:
        """_facade.py should match test_facade.py (leading _ stripped)."""
        from axm_audit.core.rules.practices.mirror import MirrorRule

        pkg = tmp_path / "src" / "pkg"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("")
        (pkg / "_facade.py").write_text("class Facade: pass\n")

        tests = tmp_path / "tests"
        tests.mkdir()
        (tests / "test_facade.py").write_text("def test_facade(): pass\n")

        rule = MirrorRule()
        result = rule.check(tmp_path)
        assert result.passed is True
        assert result.details is None or "_facade.py" not in result.details.get(
            "missing", []
        )

    def test_private_module_matches_exact_test(self, tmp_path: Path) -> None:
        """_facade.py should also match test__facade.py (exact prefix)."""
        from axm_audit.core.rules.practices.mirror import MirrorRule

        pkg = tmp_path / "src" / "pkg"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("")
        (pkg / "_facade.py").write_text("class Facade: pass\n")

        tests = tmp_path / "tests"
        tests.mkdir()
        (tests / "test__facade.py").write_text("def test_facade(): pass\n")

        rule = MirrorRule()
        result = rule.check(tmp_path)
        assert result.passed is True
        assert result.details is None or "_facade.py" not in result.details.get(
            "missing", []
        )

    def test_public_module_unchanged(self, tmp_path: Path) -> None:
        """Public module base.py should still match test_base.py unchanged."""
        from axm_audit.core.rules.practices.mirror import MirrorRule

        pkg = tmp_path / "src" / "pkg"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("")
        (pkg / "base.py").write_text("class Base: pass\n")

        tests = tmp_path / "tests"
        tests.mkdir()
        (tests / "test_base.py").write_text("def test_base(): pass\n")

        rule = MirrorRule()
        result = rule.check(tmp_path)
        assert result.passed is True

    def test_private_module_no_test(self, tmp_path: Path) -> None:
        """_facade.py with no matching test should appear in missing."""
        from axm_audit.core.rules.practices.mirror import MirrorRule

        pkg = tmp_path / "src" / "pkg"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("")
        (pkg / "_facade.py").write_text("class Facade: pass\n")

        tests = tmp_path / "tests"
        tests.mkdir()
        # No test file at all

        rule = MirrorRule()
        result = rule.check(tmp_path)
        assert result.passed is False
        assert result.details is not None
        assert "_facade.py" in result.details["missing"]

    def test_double_underscore_stripped(self, tmp_path: Path) -> None:
        """__internal.py should match test_internal.py (all leading _ stripped)."""
        from axm_audit.core.rules.practices.mirror import MirrorRule

        pkg = tmp_path / "src" / "pkg"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("")
        (pkg / "__internal.py").write_text("x = 1\n")

        tests = tmp_path / "tests"
        tests.mkdir()
        (tests / "test_internal.py").write_text("def test_internal(): pass\n")

        rule = MirrorRule()
        result = rule.check(tmp_path)
        assert result.passed is True
        assert result.details is None or "__internal.py" not in result.details.get(
            "missing", []
        )

    def test_triple_underscore_stripped(self, tmp_path: Path) -> None:
        """___triple.py (pathological) should match test_triple.py."""
        from axm_audit.core.rules.practices.mirror import MirrorRule

        pkg = tmp_path / "src" / "pkg"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("")
        (pkg / "___triple.py").write_text("x = 1\n")

        tests = tmp_path / "tests"
        tests.mkdir()
        (tests / "test_triple.py").write_text("def test_triple(): pass\n")

        rule = MirrorRule()
        result = rule.check(tmp_path)
        assert result.passed is True
        assert result.details is None or "___triple.py" not in result.details.get(
            "missing", []
        )

    # --- Pyramid scoping: mirror only counts unit-level tests ---

    def test_unit_dir_present_only_unit_counts(self, tmp_path: Path) -> None:
        """When tests/unit/ exists, integration/e2e tests do not satisfy the mirror."""
        from axm_audit.core.rules.practices.mirror import MirrorRule

        pkg = tmp_path / "src" / "pkg"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("")
        (pkg / "foo.py").write_text("def foo(): pass\n")

        unit = tmp_path / "tests" / "unit"
        unit.mkdir(parents=True)
        integ = tmp_path / "tests" / "integration"
        integ.mkdir(parents=True)
        (integ / "test_foo.py").write_text("def test_foo(): pass\n")

        rule = MirrorRule()
        result = rule.check(tmp_path)
        assert result.passed is False
        assert result.details is not None
        assert "foo.py" in result.details["missing"]

    def test_flat_layout_excludes_integration_and_e2e(self, tmp_path: Path) -> None:
        """In flat layout (no tests/unit/), integration/e2e subdirs are excluded."""
        from axm_audit.core.rules.practices.mirror import MirrorRule

        pkg = tmp_path / "src" / "pkg"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("")
        (pkg / "foo.py").write_text("def foo(): pass\n")

        e2e = tmp_path / "tests" / "e2e"
        e2e.mkdir(parents=True)
        (e2e / "test_foo.py").write_text("def test_foo(): pass\n")

        rule = MirrorRule()
        result = rule.check(tmp_path)
        assert result.passed is False
        assert result.details is not None
        assert "foo.py" in result.details["missing"]


# ─── MirrorRule reverse / orphan check (AXM-1665) ────────────────────────────


def _write(path: Path, content: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


class TestMirrorRuleOrphanIntegration:
    """Reverse mirror check — orphan unit tests (AC1-AC9)."""

    def test_orphan_test_no_matching_source(self, tmp_path: Path) -> None:
        """AC1: a tests/unit/test_*.py with no matching src module is orphan."""
        from axm_audit.core.rules.practices.mirror import MirrorRule

        _write(tmp_path / "src" / "pkg" / "__init__.py")
        _write(tmp_path / "src" / "pkg" / "foo.py", "x = 1\n")
        _write(tmp_path / "tests" / "unit" / "test_foo.py", "")
        _write(tmp_path / "tests" / "unit" / "test_ghost.py", "")

        result = MirrorRule().check(tmp_path)

        assert result.passed is False
        assert result.details is not None
        orphan = result.details["orphan"]
        assert any("test_ghost.py" in o for o in orphan)
        assert "foo.py" not in result.details["missing"]

    def test_orphan_test_misplaced_arborescence(self, tmp_path: Path) -> None:
        """AC2: a test at tests/unit/ root that should mirror a nested src is orphan."""
        from axm_audit.core.rules.practices.mirror import MirrorRule

        _write(tmp_path / "src" / "pkg" / "__init__.py")
        _write(tmp_path / "src" / "pkg" / "sub" / "__init__.py")
        _write(tmp_path / "src" / "pkg" / "sub" / "foo.py", "x = 1\n")
        _write(tmp_path / "tests" / "unit" / "test_foo.py", "")

        result = MirrorRule().check(tmp_path)

        assert result.passed is False
        assert result.details is not None
        orphan = result.details["orphan"]
        assert any("test_foo.py" in o for o in orphan)
        assert "foo.py" in result.details["missing"]

    def test_orphan_correct_arborescence_passes(self, tmp_path: Path) -> None:
        """AC2: a properly-nested test mirroring its src is not orphan."""
        from axm_audit.core.rules.practices.mirror import MirrorRule

        _write(tmp_path / "src" / "pkg" / "__init__.py")
        _write(tmp_path / "src" / "pkg" / "sub" / "__init__.py")
        _write(tmp_path / "src" / "pkg" / "sub" / "foo.py", "x = 1\n")
        _write(tmp_path / "tests" / "unit" / "sub" / "test_foo.py", "")

        result = MirrorRule().check(tmp_path)

        assert result.passed is True
        assert result.details is not None
        assert result.details["orphan"] == []

    def test_orphan_details_key_distinct_from_missing(self, tmp_path: Path) -> None:
        """AC3: details['orphan'] and details['missing'] are disjoint."""
        from axm_audit.core.rules.practices.mirror import MirrorRule

        _write(tmp_path / "src" / "pkg" / "__init__.py")
        _write(tmp_path / "src" / "pkg" / "alpha.py", "x = 1\n")
        _write(tmp_path / "src" / "pkg" / "beta.py", "x = 1\n")
        _write(tmp_path / "tests" / "unit" / "test_alpha.py", "")
        _write(tmp_path / "tests" / "unit" / "test_orphanxyz.py", "")

        result = MirrorRule().check(tmp_path)

        assert result.details is not None
        missing = result.details["missing"]
        orphan = result.details["orphan"]
        assert missing
        assert orphan
        orphan_basenames = {Path(o).name for o in orphan}
        assert set(missing).isdisjoint(orphan_basenames)

    def test_orphan_fix_hint_suggests_close_match(self, tmp_path: Path) -> None:
        """AC4: fix_hint proposes the closest source basename for typos."""
        from axm_audit.core.rules.practices.mirror import MirrorRule

        _write(tmp_path / "src" / "pkg" / "__init__.py")
        _write(tmp_path / "src" / "pkg" / "helpers.py", "x = 1\n")
        _write(tmp_path / "tests" / "unit" / "test_helpres.py", "")

        result = MirrorRule().check(tmp_path)

        assert result.fix_hint is not None
        assert "rename" in result.fix_hint.lower()
        assert "test_helpers.py" in result.fix_hint

    def test_orphan_fix_hint_no_close_match(self, tmp_path: Path) -> None:
        """AC4: fix_hint mentions orphan + suggests delete/rename when no match."""
        from axm_audit.core.rules.practices.mirror import MirrorRule

        _write(tmp_path / "src" / "pkg" / "__init__.py")
        _write(tmp_path / "src" / "pkg" / "foo.py", "x = 1\n")
        _write(tmp_path / "tests" / "unit" / "test_zzzzqqqq.py", "")

        result = MirrorRule().check(tmp_path)

        assert result.fix_hint is not None
        assert "test_zzzzqqqq.py" in result.fix_hint
        hint_lower = result.fix_hint.lower()
        assert "delete" in hint_lower or "rename" in hint_lower

    def test_orphan_text_line_present(self, tmp_path: Path) -> None:
        """AC5: result.text contains a '• orphan:' bullet line."""
        from axm_audit.core.rules.practices.mirror import MirrorRule

        _write(tmp_path / "src" / "pkg" / "__init__.py")
        _write(tmp_path / "src" / "pkg" / "foo.py", "x = 1\n")
        _write(tmp_path / "tests" / "unit" / "test_foo.py", "")
        _write(tmp_path / "tests" / "unit" / "test_ghost.py", "")

        result = MirrorRule().check(tmp_path)

        assert result.text is not None
        assert any(line.startswith("• orphan:") for line in result.text.splitlines())

    def test_score_penalizes_both_directions(self, tmp_path: Path) -> None:
        """AC6: 1 missing + 1 orphan → score == 70."""
        from axm_audit.core.rules.practices.mirror import MirrorRule

        _write(tmp_path / "src" / "pkg" / "__init__.py")
        _write(tmp_path / "src" / "pkg" / "foo.py", "x = 1\n")
        _write(tmp_path / "src" / "pkg" / "bar.py", "x = 1\n")
        _write(tmp_path / "tests" / "unit" / "test_foo.py", "")
        _write(tmp_path / "tests" / "unit" / "test_ghost.py", "")

        result = MirrorRule().check(tmp_path)

        assert result.score == 70

    def test_score_one_orphan_only(self, tmp_path: Path) -> None:
        """AC6: 0 missing + 1 orphan → score == 85."""
        from axm_audit.core.rules.practices.mirror import MirrorRule

        _write(tmp_path / "src" / "pkg" / "__init__.py")
        _write(tmp_path / "src" / "pkg" / "foo.py", "x = 1\n")
        _write(tmp_path / "tests" / "unit" / "test_foo.py", "")
        _write(tmp_path / "tests" / "unit" / "test_ghost.py", "")

        result = MirrorRule().check(tmp_path)

        assert result.score == 85

    def test_integration_test_not_flagged_as_orphan(self, tmp_path: Path) -> None:
        """AC7: tests/integration/ files are never orphans."""
        from axm_audit.core.rules.practices.mirror import MirrorRule

        _write(tmp_path / "src" / "pkg" / "__init__.py")
        _write(tmp_path / "src" / "pkg" / "foo.py", "x = 1\n")
        _write(tmp_path / "tests" / "unit" / "test_foo.py", "")
        _write(tmp_path / "tests" / "integration" / "test_anything.py", "")

        result = MirrorRule().check(tmp_path)

        assert result.passed is True
        assert result.details is not None
        assert result.details["orphan"] == []

    def test_e2e_test_not_flagged_as_orphan(self, tmp_path: Path) -> None:
        """AC7: tests/e2e/ files are never orphans."""
        from axm_audit.core.rules.practices.mirror import MirrorRule

        _write(tmp_path / "src" / "pkg" / "__init__.py")
        _write(tmp_path / "src" / "pkg" / "foo.py", "x = 1\n")
        _write(tmp_path / "tests" / "unit" / "test_foo.py", "")
        _write(tmp_path / "tests" / "e2e" / "test_anything.py", "")

        result = MirrorRule().check(tmp_path)

        assert result.passed is True
        assert result.details is not None
        assert result.details["orphan"] == []

    def test_orphan_init_and_conftest_excluded(self, tmp_path: Path) -> None:
        """AC8: __init__.py and conftest.py under tests/unit/ are exempt."""
        from axm_audit.core.rules.practices.mirror import MirrorRule

        _write(tmp_path / "src" / "pkg" / "__init__.py")
        _write(tmp_path / "src" / "pkg" / "foo.py", "x = 1\n")
        _write(tmp_path / "tests" / "unit" / "test_foo.py", "")
        _write(tmp_path / "tests" / "unit" / "__init__.py", "")
        _write(tmp_path / "tests" / "unit" / "conftest.py", "")

        result = MirrorRule().check(tmp_path)

        assert result.passed is True
        assert result.details is not None
        assert result.details["orphan"] == []

    def test_no_unit_dir_no_orphan_check(self, tmp_path: Path) -> None:
        """AC9: legacy flat layout (no tests/unit/) skips reverse check."""
        from axm_audit.core.rules.practices.mirror import MirrorRule

        _write(tmp_path / "src" / "pkg" / "__init__.py")
        _write(tmp_path / "src" / "pkg" / "foo.py", "x = 1\n")
        _write(tmp_path / "tests" / "test_foo.py", "")

        result = MirrorRule().check(tmp_path)

        assert result.passed is True
        assert result.details is not None
        assert result.details["orphan"] == []

    def test_empty_unit_dir_no_orphan(self, tmp_path: Path) -> None:
        """AC9: empty tests/unit/ produces no orphans."""
        from axm_audit.core.rules.practices.mirror import MirrorRule

        _write(tmp_path / "src" / "pkg" / "__init__.py")
        _write(tmp_path / "src" / "pkg" / "foo.py", "x = 1\n")
        (tmp_path / "tests" / "unit").mkdir(parents=True)
        _write(tmp_path / "tests" / "test_foo.py", "")

        result = MirrorRule().check(tmp_path)

        assert result.passed is True
        assert result.details is not None
        assert result.details["orphan"] == []
