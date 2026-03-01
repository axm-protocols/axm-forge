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
