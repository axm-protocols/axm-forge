"""Tests for Practice Rules — RED phase."""

from pathlib import Path


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
