"""Split from ``test_practices.py``."""

from pathlib import Path

import pytest

from axm_audit.core.rules.security import SecurityPatternRule


def _scan_secret_count(tmp_path: Path, source: str) -> int:
    """Drive the public boundary: write source under src/ and count secret matches."""
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "mod.py").write_text(source)
    result = SecurityPatternRule().check(tmp_path)
    assert result.details is not None
    count = result.details["secret_count"]
    assert isinstance(count, int)
    return count


@pytest.mark.integration
def test_placeholder_password_not_flagged(tmp_path: Path) -> None:
    """AC2: a placeholder password value ('changeme') yields 0 secret matches."""
    assert _scan_secret_count(tmp_path, 'password = "changeme"\n') == 0


@pytest.mark.integration
def test_angle_bracket_placeholder_not_flagged(tmp_path: Path) -> None:
    """AC2: an angle-bracket placeholder ('<your-key>') yields 0 matches."""
    assert _scan_secret_count(tmp_path, 'api_key = "<your-key>"\n') == 0


@pytest.mark.integration
def test_real_hex_secret_flagged(tmp_path: Path) -> None:
    """AC4: a real-looking 40-char hex token assigned to secret is flagged."""
    hex_token = "a3f9c1" + "0" * 34
    assert _scan_secret_count(tmp_path, f'secret = "{hex_token}"\n') == 1


@pytest.mark.integration
def test_ellipsis_example_value_not_flagged(tmp_path: Path) -> None:
    """An elided example value (literal ``...``) is a placeholder, not a secret."""
    assert _scan_secret_count(tmp_path, 'api_key = "..."\n') == 0


@pytest.mark.integration
def test_truncated_token_example_not_flagged(tmp_path: Path) -> None:
    """A truncated token example (``ghp_...``) carries an ellipsis -> placeholder."""
    assert _scan_secret_count(tmp_path, 'token = "ghp_..."\n') == 0


@pytest.mark.integration
def test_long_truncated_example_not_flagged(tmp_path: Path) -> None:
    """Even a long example value is a placeholder when it contains ``...``."""
    assert (
        _scan_secret_count(tmp_path, 'api_key = "sk_live_abcdef...0123456789xyz"\n')
        == 0
    )


@pytest.mark.integration
def test_rule_does_not_flag_own_pattern_definitions(tmp_path: Path) -> None:
    """The rule must not flag its own explanatory pattern-definition source.

    Regression for the self-referential false positive where the comments
    ``api_key = "..."`` and ``token = "ghp_..."`` inside this module's source
    were reported as leaked secrets (PRACTICE_SECURITY at security.py:259/335).
    """
    import inspect

    own_source = Path(inspect.getfile(SecurityPatternRule)).read_text()
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "mod.py").write_text(own_source)
    result = SecurityPatternRule().check(tmp_path)
    assert result.details is not None
    assert result.details["secret_count"] == 0, result.details["matches"]


@pytest.mark.integration
def test_real_github_token_still_flagged(tmp_path: Path) -> None:
    """No weakening: a full 36-char GitHub PAT (no ellipsis) is still flagged."""
    real_pat = "ghp_" + "a1B2c3" * 6  # 36 alnum chars after the prefix
    assert _scan_secret_count(tmp_path, f'token = "{real_pat}"\n') == 1


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


@pytest.fixture
def rule() -> SecurityPatternRule:
    return SecurityPatternRule()


@pytest.mark.integration
def test_aws_github_pem_detected(tmp_path: Path) -> None:
    """AC1: AWS AKIA key, GitHub ghp_ token, and PEM private-key header each flagged."""
    aws = "AKIA" + "A1B2C3D4E5F6G7H8"
    gh = "ghp_" + "a" * 36
    pem = "-----BEGIN PRIVATE KEY-----"
    _make_src_file(tmp_path, "aws.py", f'key = "{aws}"\n')
    _make_src_file(tmp_path, "gh.py", f'token = "{gh}"\n')
    _make_src_file(tmp_path, "pem.py", f'blob = """{pem}"""\n')
    result = SecurityPatternRule().check(tmp_path)
    assert result.details is not None
    assert result.details["secret_count"] == 3


@pytest.mark.integration
def test_fixture_placeholders_clean(tmp_path: Path) -> None:
    """AC2,AC3: a file full of placeholder assignments yields 0 findings."""
    source = (
        'password = "changeme"\n'
        'secret = "xxx"\n'
        'api_key = "<token>"\n'
        'token = "example"\n'
        'password = "placeholder"\n'
        'secret = "dummy"\n'
        'api_key = "test"\n'
        'token = "redacted"\n'
        'password = "********"\n'
    )
    _make_src_file(tmp_path, "fixtures.py", source)
    result = SecurityPatternRule().check(tmp_path)
    assert result.details is not None
    assert result.details["secret_count"] == 0


def _make_src_file(tmp_path: Path, filename: str, content: str) -> None:
    src = tmp_path / "src"
    src.mkdir(exist_ok=True)
    (src / filename).write_text(content)


def test_fail_text_contains_matches(tmp_path: Path, rule: SecurityPatternRule) -> None:
    """result.text contains one bullet per match when secrets are found."""
    _make_src_file(
        tmp_path,
        "bad.py",
        'password = "super_secret_123"\napi_key = "sk-live-9f8e7d6c5b4a"\n',
    )
    result = rule.check(tmp_path)

    assert result.text is not None
    assert "\u2022 bad.py:" in result.text
    lines = result.text.strip().split("\n")
    assert len(lines) == 2


def test_pass_text_is_none(tmp_path: Path, rule: SecurityPatternRule) -> None:
    """result.text is None when no secrets are found."""
    _make_src_file(tmp_path, "clean.py", "x = 1\ny = 2\n")
    result = rule.check(tmp_path)

    assert result.text is None


def test_text_bullet_format(tmp_path: Path, rule: SecurityPatternRule) -> None:
    """Bullet format: 5-space indent + bullet + file:line + pattern."""
    _make_src_file(tmp_path, "bad.py", '\npassword = "super_secret_123"\n')
    result = rule.check(tmp_path)

    assert result.text is not None
    assert result.text == "\u2022 bad.py:2 password"


def test_early_result_no_text(tmp_path: Path, rule: SecurityPatternRule) -> None:
    """No src/ directory -> early result has no text."""
    result = rule.check(tmp_path)

    assert result.text is None


def test_multiple_patterns_same_file(tmp_path: Path, rule: SecurityPatternRule) -> None:
    """Multiple matches produce one bullet each with correct line numbers."""
    _make_src_file(
        tmp_path,
        "bad.py",
        'password = "super_secret_123"\nsecret = "another_real_value_456"\n',
    )
    result = rule.check(tmp_path)

    assert result.text is not None
    lines = result.text.strip().split("\n")
    assert len(lines) == 2
    assert "bad.py:1" in lines[0]
    assert "bad.py:2" in lines[1]
