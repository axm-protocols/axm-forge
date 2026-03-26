"""Tests for Practice Rules — RED phase."""

from pathlib import Path

from axm_audit.models.results import Severity


class TestDocstringCoverageRule:
    """Tests for DocstringCoverageRule."""

    def test_fully_documented_passes(self, tmp_path: Path) -> None:
        """All public functions with docstrings should pass."""
        from axm_audit.core.rules.practices import DocstringCoverageRule

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
        from axm_audit.core.rules.practices import DocstringCoverageRule

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
        from axm_audit.core.rules.practices import DocstringCoverageRule

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

    def test_rule_id_format(self) -> None:
        """Rule ID should be PRACTICE_DOCSTRING."""
        from axm_audit.core.rules.practices import DocstringCoverageRule

        rule = DocstringCoverageRule()
        assert rule.rule_id == "PRACTICE_DOCSTRING"


class TestBareExceptRule:
    """Tests for BareExceptRule."""

    def test_typed_except_passes(self, tmp_path: Path) -> None:
        """Typed except clauses should pass."""
        from axm_audit.core.rules.practices import BareExceptRule

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
        from axm_audit.core.rules.practices import BareExceptRule

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

    def test_rule_id_format(self) -> None:
        """Rule ID should be PRACTICE_BARE_EXCEPT."""
        from axm_audit.core.rules.practices import BareExceptRule

        rule = BareExceptRule()
        assert rule.rule_id == "PRACTICE_BARE_EXCEPT"

    def test_find_bare_excepts_helper(self, tmp_path: Path) -> None:
        """Tests that _find_bare_excepts correctly extracts locations."""
        import ast

        from axm_audit.core.rules.practices import BareExceptRule

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


class TestSecurityPatternRule:
    """Tests for SecurityPatternRule."""

    def test_no_secrets_passes(self, tmp_path: Path) -> None:
        """Code without hardcoded secrets should pass."""
        from axm_audit.core.rules.practices import SecurityPatternRule

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
        from axm_audit.core.rules.practices import SecurityPatternRule

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

    def test_rule_id_format(self) -> None:
        """Rule ID should be PRACTICE_SECURITY."""
        from axm_audit.core.rules.practices import SecurityPatternRule

        rule = SecurityPatternRule()
        assert rule.rule_id == "PRACTICE_SECURITY"


# ─── BlockingIORule ──────────────────────────────────────────────────────────


class TestBlockingIORule:
    """Tests for BlockingIORule."""

    def test_pass_no_blocking(self, tmp_path: Path) -> None:
        """Module with async def using asyncio.sleep should pass."""
        from axm_audit.core.rules.practices import BlockingIORule

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
        from axm_audit.core.rules.practices import BlockingIORule

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
        from axm_audit.core.rules.practices import BlockingIORule

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
        from axm_audit.core.rules.practices import BlockingIORule

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
        from axm_audit.core.rules.practices import BlockingIORule

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

    def test_rule_id_format(self) -> None:
        """Rule ID should be PRACTICE_BLOCKING_IO."""
        from axm_audit.core.rules.practices import BlockingIORule

        rule = BlockingIORule()
        assert rule.rule_id == "PRACTICE_BLOCKING_IO"


# ─── LoggingPresenceRule ─────────────────────────────────────────────────────


class TestLoggingPresenceRule:
    """Tests for LoggingPresenceRule."""

    def test_pass_all_log(self, tmp_path: Path) -> None:
        """All substantial modules importing logging should pass."""
        from axm_audit.core.rules.practices import LoggingPresenceRule

        src = tmp_path / "src" / "pkg"
        src.mkdir(parents=True)
        funcs = "\n".join(f"def func_{i}():\n    pass\n" for i in range(6))
        (src / "mod.py").write_text(f"import logging\n\n{funcs}")

        rule = LoggingPresenceRule()
        result = rule.check(tmp_path)
        assert result.passed is True

    def test_fail_no_logging(self, tmp_path: Path) -> None:
        """Substantial module without logging import should fail."""
        from axm_audit.core.rules.practices import LoggingPresenceRule

        src = tmp_path / "src" / "pkg"
        src.mkdir(parents=True)
        funcs = "\n".join(f"def func_{i}():\n    pass\n" for i in range(6))
        (src / "mod.py").write_text(funcs)

        rule = LoggingPresenceRule()
        result = rule.check(tmp_path)
        assert result.passed is False
        assert result.details is not None
        assert len(result.details["without_logging"]) == 1

    def test_exempt_small_module(self, tmp_path: Path) -> None:
        """Module with < 5 definitions should be exempt."""
        from axm_audit.core.rules.practices import LoggingPresenceRule

        src = tmp_path / "src" / "pkg"
        src.mkdir(parents=True)
        (src / "small.py").write_text("def a():\n    pass\n\ndef b():\n    pass\n")

        rule = LoggingPresenceRule()
        result = rule.check(tmp_path)
        assert result.passed is True

    def test_no_src_directory(self, tmp_path: Path) -> None:
        """Empty project without src/ should pass with INFO."""
        from axm_audit.core.rules.practices import LoggingPresenceRule

        rule = LoggingPresenceRule()
        result = rule.check(tmp_path)
        assert result.passed is True
        assert result.severity == Severity.INFO

    def test_from_logging_import(self, tmp_path: Path) -> None:
        """'from logging import getLogger' should count as logging present."""
        from axm_audit.core.rules.practices import LoggingPresenceRule

        src = tmp_path / "src" / "pkg"
        src.mkdir(parents=True)
        funcs = "\n".join(f"def func_{i}():\n    pass\n" for i in range(6))
        (src / "mod.py").write_text(f"from logging import getLogger\n\n{funcs}")

        rule = LoggingPresenceRule()
        result = rule.check(tmp_path)
        assert result.passed is True

    def test_rule_id_format(self) -> None:
        """Rule ID should be PRACTICE_LOGGING."""
        from axm_audit.core.rules.practices import LoggingPresenceRule

        rule = LoggingPresenceRule()
        assert rule.rule_id == "PRACTICE_LOGGING"


# ─── LoggingPresenceRule — data module exemption ─────────────────────────────


class TestLoggingPresenceDataModuleExemption:
    """Tests for pure data module exemption from PRACTICE_LOGGING."""

    def test_pure_basemodel_module_excluded(self, tmp_path: Path) -> None:
        """Module with only BaseModel subclasses should be excluded."""
        import ast

        from axm_audit.core.rules.practices import LoggingPresenceRule

        source = """
from pydantic import BaseModel

class UserConfig(BaseModel):
    name: str
    age: int

class Address(BaseModel):
    street: str
    city: str

class Settings(BaseModel):
    debug: bool

class Metadata(BaseModel):
    version: str

class Output(BaseModel):
    result: str
"""
        tree = ast.parse(source)
        rule = LoggingPresenceRule()
        path = tmp_path / "models.py"
        path.write_text(source)
        assert rule._should_check_module(path, tree) is False

    def test_mixed_module_still_checked(self, tmp_path: Path) -> None:
        """Module with BaseModel + standalone functions should still be checked."""
        import ast

        from axm_audit.core.rules.practices import LoggingPresenceRule

        source = """
from pydantic import BaseModel

class UserConfig(BaseModel):
    name: str

class Address(BaseModel):
    street: str

def process_user(user: UserConfig) -> str:
    return user.name

def validate_address(addr: Address) -> bool:
    return bool(addr.street)

def format_output() -> str:
    return "done"
"""
        tree = ast.parse(source)
        rule = LoggingPresenceRule()
        path = tmp_path / "mixed.py"
        path.write_text(source)
        assert rule._should_check_module(path, tree) is True

    def test_typed_dict_module_excluded(self, tmp_path: Path) -> None:
        """Module with only TypedDict classes should be excluded."""
        import ast

        from axm_audit.core.rules.practices import LoggingPresenceRule

        source = """
from typing import TypedDict

class UserDict(TypedDict):
    name: str
    age: int

class AddressDict(TypedDict):
    street: str
    city: str

class ConfigDict(TypedDict):
    debug: bool

class MetaDict(TypedDict):
    version: str

class OutputDict(TypedDict):
    result: str
"""
        tree = ast.parse(source)
        rule = LoggingPresenceRule()
        path = tmp_path / "types.py"
        path.write_text(source)
        assert rule._should_check_module(path, tree) is False

    def test_enum_module_excluded(self, tmp_path: Path) -> None:
        """Module with only Enum classes should be excluded."""
        import ast

        from axm_audit.core.rules.practices import LoggingPresenceRule

        source = """
from enum import Enum

class Color(Enum):
    RED = 1
    GREEN = 2

class Status(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"

class Priority(Enum):
    LOW = 0
    HIGH = 1

class Direction(Enum):
    UP = "up"
    DOWN = "down"

class Mode(Enum):
    FAST = "fast"
    SLOW = "slow"
"""
        tree = ast.parse(source)
        rule = LoggingPresenceRule()
        path = tmp_path / "enums.py"
        path.write_text(source)
        assert rule._should_check_module(path, tree) is False

    def test_validator_functions_excluded(self, tmp_path: Path) -> None:
        """Module with BaseModel + @field_validator helper defs should be excluded."""
        import ast

        from axm_audit.core.rules.practices import LoggingPresenceRule

        source = """
from pydantic import BaseModel, field_validator

class UserConfig(BaseModel):
    name: str
    age: int

    @field_validator("age")
    @classmethod
    def validate_age(cls, v: int) -> int:
        if v < 0:
            raise ValueError("Age must be positive")
        return v

class Address(BaseModel):
    street: str
    city: str

class Settings(BaseModel):
    debug: bool

class Metadata(BaseModel):
    version: str

class Output(BaseModel):
    result: str
"""
        tree = ast.parse(source)
        rule = LoggingPresenceRule()
        path = tmp_path / "validated_models.py"
        path.write_text(source)
        assert rule._should_check_module(path, tree) is False

    def test_module_level_constants_excluded(self, tmp_path: Path) -> None:
        """Data module with module-level constants should still be excluded."""
        import ast

        from axm_audit.core.rules.practices import LoggingPresenceRule

        source = """
from pydantic import BaseModel

SECTION_MODELS: dict = {"a": 1, "b": 2}
DEFAULT_TIMEOUT = 30

class UserConfig(BaseModel):
    name: str

class Address(BaseModel):
    street: str

class Settings(BaseModel):
    debug: bool

class Metadata(BaseModel):
    version: str

class Output(BaseModel):
    result: str
"""
        tree = ast.parse(source)
        rule = LoggingPresenceRule()
        path = tmp_path / "constants_models.py"
        path.write_text(source)
        assert rule._should_check_module(path, tree) is False

    def test_mixed_inheritance_still_checked(self, tmp_path: Path) -> None:
        """Class inheriting both BaseModel and a mixin should still be checked."""
        import ast

        from axm_audit.core.rules.practices import LoggingPresenceRule

        source = """
from pydantic import BaseModel

class LoggableMixin:
    pass

class UserConfig(BaseModel, LoggableMixin):
    name: str

class Address(BaseModel, LoggableMixin):
    street: str

class Settings(BaseModel, LoggableMixin):
    debug: bool

class Metadata(BaseModel, LoggableMixin):
    version: str

class Output(BaseModel, LoggableMixin):
    result: str
"""
        tree = ast.parse(source)
        rule = LoggingPresenceRule()
        path = tmp_path / "mixed_inherit.py"
        path.write_text(source)
        assert rule._should_check_module(path, tree) is True


# ─── Docstring detail coverage ───────────────────────────────────────────────


class TestDocstringMissingDetail:
    """Tests for missing docstring listing (no cap, all items shown)."""

    def test_missing_no_cap(self, tmp_path: Path) -> None:
        """All missing docstrings are returned, not capped at 10."""
        from axm_audit.core.rules.practices import DocstringCoverageRule

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
        from axm_audit.core.rules.practices import DocstringCoverageRule

        src = tmp_path / "src"
        src.mkdir()
        (src / "mod.py").write_text("def foo() -> None:\n    pass\n")

        rule = DocstringCoverageRule()
        result = rule.check(tmp_path)
        assert result.details is not None
        assert any("foo" in m for m in result.details["missing"])

    def test_fully_documented_empty_missing(self, tmp_path: Path) -> None:
        """100% coverage returns empty missing list."""
        from axm_audit.core.rules.practices import DocstringCoverageRule

        src = tmp_path / "src"
        src.mkdir()
        (src / "ok.py").write_text('def ok() -> None:\n    """Ok."""\n    pass\n')

        rule = DocstringCoverageRule()
        result = rule.check(tmp_path)
        assert result.details is not None
        assert result.details["missing"] == []


# ─── format_agent actionable detail ──────────────────────────────────────────


class TestFormatAgentActionable:
    """Tests for format_agent surfacing details on passed checks."""

    def test_passed_with_missing_includes_details(self) -> None:
        """Passed check with missing docstrings includes full details."""
        from axm_audit.formatters import format_agent
        from axm_audit.models.results import AuditResult, CheckResult, Severity

        check = CheckResult(
            rule_id="PRACTICE_DOCSTRING",
            passed=True,
            message="Docstring coverage: 88% (7/8)",
            severity=Severity.INFO,
            details={
                "coverage": 0.88,
                "total": 8,
                "documented": 7,
                "missing": ["mod.py:foo"],
            },
            fix_hint="Add docstrings to public functions",
        )
        result = AuditResult(checks=[check])
        output = format_agent(result)

        # Passed entry should be a dict with details, not a plain string
        assert len(output["passed"]) == 1
        entry = output["passed"][0]
        assert isinstance(entry, dict)
        assert entry["details"]["missing"] == ["mod.py:foo"]

    def test_passed_clean_is_string(self) -> None:
        """Passed check with no actionable items stays as summary string."""
        from axm_audit.formatters import format_agent
        from axm_audit.models.results import AuditResult, CheckResult, Severity

        check = CheckResult(
            rule_id="QUALITY_TYPE",
            passed=True,
            message="Type score: 100/100",
            severity=Severity.INFO,
            details={"score": 100},
        )
        result = AuditResult(checks=[check])
        output = format_agent(result)

        assert len(output["passed"]) == 1
        assert isinstance(output["passed"][0], str)

    def test_passed_empty_missing_is_string(self) -> None:
        """Passed check with empty missing list stays as summary string."""
        from axm_audit.formatters import format_agent
        from axm_audit.models.results import AuditResult, CheckResult, Severity

        check = CheckResult(
            rule_id="PRACTICE_DOCSTRING",
            passed=True,
            message="Docstring coverage: 100% (8/8)",
            severity=Severity.INFO,
            details={"coverage": 1.0, "total": 8, "documented": 8, "missing": []},
        )
        result = AuditResult(checks=[check])
        output = format_agent(result)

        assert len(output["passed"]) == 1
        assert isinstance(output["passed"][0], str)


# ─── TestMirrorRule ──────────────────────────────────────────────────────────


class TestTestMirrorRule:
    """Tests for TestMirrorRule — 1:1 source-to-test file mapping."""

    def test_pass_all_modules_tested(self, tmp_path: Path) -> None:
        """All source modules with matching test files should pass."""
        from axm_audit.core.rules.practices import TestMirrorRule

        pkg = tmp_path / "src" / "pkg"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("")
        (pkg / "a.py").write_text("def hello(): pass\n")
        (pkg / "b.py").write_text("def world(): pass\n")

        tests = tmp_path / "tests"
        tests.mkdir()
        (tests / "test_a.py").write_text("def test_a(): pass\n")
        (tests / "test_b.py").write_text("def test_b(): pass\n")

        rule = TestMirrorRule()
        result = rule.check(tmp_path)
        assert result.passed is True
        assert result.fix_hint is None

    def test_fail_missing_tests(self, tmp_path: Path) -> None:
        """Missing test file should fail with details listing the module."""
        from axm_audit.core.rules.practices import TestMirrorRule

        pkg = tmp_path / "src" / "pkg"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("")
        (pkg / "a.py").write_text("def hello(): pass\n")
        (pkg / "b.py").write_text("def world(): pass\n")

        tests = tmp_path / "tests"
        tests.mkdir()
        (tests / "test_a.py").write_text("def test_a(): pass\n")
        # No test_b.py!

        rule = TestMirrorRule()
        result = rule.check(tmp_path)
        assert result.passed is False
        assert result.details is not None
        assert "b.py" in result.details["missing"]
        assert result.fix_hint is not None
        assert "test_b.py" in result.fix_hint

    def test_exempt_init_and_version(self, tmp_path: Path) -> None:
        """__init__.py and _version.py should be exempt from test requirement."""
        from axm_audit.core.rules.practices import TestMirrorRule

        pkg = tmp_path / "src" / "pkg"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("")
        (pkg / "_version.py").write_text("__version__ = '0.1'\n")
        (pkg / "a.py").write_text("def hello(): pass\n")

        tests = tmp_path / "tests"
        tests.mkdir()
        (tests / "test_a.py").write_text("def test_a(): pass\n")

        rule = TestMirrorRule()
        result = rule.check(tmp_path)
        assert result.passed is True

    def test_nested_test_dirs(self, tmp_path: Path) -> None:
        """Test files in nested directories (tests/core/) should match."""
        from axm_audit.core.rules.practices import TestMirrorRule

        pkg = tmp_path / "src" / "pkg"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("")
        (pkg / "foo.py").write_text("def foo(): pass\n")

        tests = tmp_path / "tests" / "core"
        tests.mkdir(parents=True)
        (tests / "test_foo.py").write_text("def test_foo(): pass\n")

        rule = TestMirrorRule()
        result = rule.check(tmp_path)
        assert result.passed is True

    def test_no_src_directory(self, tmp_path: Path) -> None:
        """Empty project without src/ should pass with INFO."""
        from axm_audit.core.rules.practices import TestMirrorRule

        rule = TestMirrorRule()
        result = rule.check(tmp_path)
        assert result.passed is True
        assert result.severity == Severity.INFO

    def test_empty_src_only_init(self, tmp_path: Path) -> None:
        """Package with only __init__.py should pass (all exempt)."""
        from axm_audit.core.rules.practices import TestMirrorRule

        pkg = tmp_path / "src" / "pkg"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("")

        rule = TestMirrorRule()
        result = rule.check(tmp_path)
        assert result.passed is True

    def test_rule_id_format(self) -> None:
        """Rule ID should be PRACTICE_TEST_MIRROR."""
        from axm_audit.core.rules.practices import TestMirrorRule

        rule = TestMirrorRule()
        assert rule.rule_id == "PRACTICE_TEST_MIRROR"

    # --- AXM-857: private module underscore stripping ---

    def test_private_module_matches_stripped_test(self, tmp_path: Path) -> None:
        """_facade.py should match test_facade.py (leading _ stripped)."""
        from axm_audit.core.rules.practices import TestMirrorRule

        pkg = tmp_path / "src" / "pkg"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("")
        (pkg / "_facade.py").write_text("class Facade: pass\n")

        tests = tmp_path / "tests"
        tests.mkdir()
        (tests / "test_facade.py").write_text("def test_facade(): pass\n")

        rule = TestMirrorRule()
        result = rule.check(tmp_path)
        assert result.passed is True
        assert result.details is None or "_facade.py" not in result.details.get(
            "missing", []
        )

    def test_private_module_matches_exact_test(self, tmp_path: Path) -> None:
        """_facade.py should also match test__facade.py (exact prefix)."""
        from axm_audit.core.rules.practices import TestMirrorRule

        pkg = tmp_path / "src" / "pkg"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("")
        (pkg / "_facade.py").write_text("class Facade: pass\n")

        tests = tmp_path / "tests"
        tests.mkdir()
        (tests / "test__facade.py").write_text("def test_facade(): pass\n")

        rule = TestMirrorRule()
        result = rule.check(tmp_path)
        assert result.passed is True
        assert result.details is None or "_facade.py" not in result.details.get(
            "missing", []
        )

    def test_public_module_unchanged(self, tmp_path: Path) -> None:
        """Public module base.py should still match test_base.py unchanged."""
        from axm_audit.core.rules.practices import TestMirrorRule

        pkg = tmp_path / "src" / "pkg"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("")
        (pkg / "base.py").write_text("class Base: pass\n")

        tests = tmp_path / "tests"
        tests.mkdir()
        (tests / "test_base.py").write_text("def test_base(): pass\n")

        rule = TestMirrorRule()
        result = rule.check(tmp_path)
        assert result.passed is True

    def test_private_module_no_test(self, tmp_path: Path) -> None:
        """_facade.py with no matching test should appear in missing."""
        from axm_audit.core.rules.practices import TestMirrorRule

        pkg = tmp_path / "src" / "pkg"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("")
        (pkg / "_facade.py").write_text("class Facade: pass\n")

        tests = tmp_path / "tests"
        tests.mkdir()
        # No test file at all

        rule = TestMirrorRule()
        result = rule.check(tmp_path)
        assert result.passed is False
        assert result.details is not None
        assert "_facade.py" in result.details["missing"]

    def test_double_underscore_stripped(self, tmp_path: Path) -> None:
        """__internal.py should match test_internal.py (all leading _ stripped)."""
        from axm_audit.core.rules.practices import TestMirrorRule

        pkg = tmp_path / "src" / "pkg"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("")
        (pkg / "__internal.py").write_text("x = 1\n")

        tests = tmp_path / "tests"
        tests.mkdir()
        (tests / "test_internal.py").write_text("def test_internal(): pass\n")

        rule = TestMirrorRule()
        result = rule.check(tmp_path)
        assert result.passed is True
        assert result.details is None or "__internal.py" not in result.details.get(
            "missing", []
        )

    def test_triple_underscore_stripped(self, tmp_path: Path) -> None:
        """___triple.py (pathological) should match test_triple.py."""
        from axm_audit.core.rules.practices import TestMirrorRule

        pkg = tmp_path / "src" / "pkg"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("")
        (pkg / "___triple.py").write_text("x = 1\n")

        tests = tmp_path / "tests"
        tests.mkdir()
        (tests / "test_triple.py").write_text("def test_triple(): pass\n")

        rule = TestMirrorRule()
        result = rule.check(tmp_path)
        assert result.passed is True
        assert result.details is None or "___triple.py" not in result.details.get(
            "missing", []
        )
