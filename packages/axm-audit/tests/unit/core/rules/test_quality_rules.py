"""Unit tests for axm_audit.core.rules.quality_rules (no I/O)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from axm_audit.core.rules.quality_rules import FormattingRule, LintingRule
from axm_audit.models import CheckResult


class TestDiffSizeRuleUnit:
    """Pure tests for DiffSizeRule (mocked subprocess, no real I/O)."""

    def test_pass_small_diff(self, tmp_path: Path) -> None:
        """Small diff (<200 lines) should pass with score 100."""
        from unittest.mock import MagicMock, patch

        from axm_audit.core.rules.quality_rules import DiffSizeRule

        # Mock git rev-parse succeeds
        rev_parse = MagicMock(returncode=0)
        # Mock git diff --stat with 50 lines changed
        diff_stat = MagicMock(
            returncode=0,
            stdout=" 3 files changed, 30 insertions(+), 20 deletions(-)\n",
        )

        with (
            patch("shutil.which", return_value="/usr/bin/git"),
            patch("subprocess.run", side_effect=[rev_parse, diff_stat]),
        ):
            rule = DiffSizeRule()
            result = rule.check(tmp_path)

        assert result.passed is True
        assert result.details is not None
        assert result.details["lines_changed"] == 50
        assert result.score == 100

    def test_fail_large_diff(self, tmp_path: Path) -> None:
        """Large diff (1100 lines) should fail with reduced score."""
        from unittest.mock import MagicMock, patch

        from axm_audit.core.rules.quality_rules import DiffSizeRule

        rev_parse = MagicMock(returncode=0)
        diff_stat = MagicMock(
            returncode=0,
            stdout=" 20 files changed, 700 insertions(+), 400 deletions(-)\n",
        )

        with (
            patch("shutil.which", return_value="/usr/bin/git"),
            patch("subprocess.run", side_effect=[rev_parse, diff_stat]),
        ):
            rule = DiffSizeRule()
            result = rule.check(tmp_path)

        assert result.passed is False
        assert result.details is not None
        assert result.details["lines_changed"] == 1100
        assert result.score == 12
        assert result.fix_hint is not None

    def test_skip_not_git_repo(self, tmp_path: Path) -> None:
        """Non-git directory should skip gracefully."""
        from unittest.mock import MagicMock, patch

        from axm_audit.core.rules.quality_rules import DiffSizeRule

        rev_parse = MagicMock(returncode=128)

        with (
            patch("shutil.which", return_value="/usr/bin/git"),
            patch("subprocess.run", return_value=rev_parse),
        ):
            rule = DiffSizeRule()
            result = rule.check(tmp_path)

        assert result.passed is True
        assert "not a git repo" in result.message

    def test_pass_no_changes(self, tmp_path: Path) -> None:
        """No uncommitted changes → pass with score 100."""
        from unittest.mock import MagicMock, patch

        from axm_audit.core.rules.quality_rules import DiffSizeRule

        rev_parse = MagicMock(returncode=0)
        diff_stat = MagicMock(returncode=0, stdout="")

        with (
            patch("shutil.which", return_value="/usr/bin/git"),
            patch("subprocess.run", side_effect=[rev_parse, diff_stat]),
        ):
            rule = DiffSizeRule()
            result = rule.check(tmp_path)

        assert result.passed is True
        assert result.details is not None
        assert result.details["lines_changed"] == 0
        assert result.score == 100

    def test_skip_git_not_installed(self, tmp_path: Path) -> None:
        """Missing git binary should skip gracefully."""
        from unittest.mock import patch

        from axm_audit.core.rules.quality_rules import DiffSizeRule

        with patch("shutil.which", return_value=None):
            rule = DiffSizeRule()
            result = rule.check(tmp_path)

        assert result.passed is True
        assert "git not installed" in result.message

    def test_rule_id_format(self) -> None:
        """Rule ID should be QUALITY_DIFF_SIZE."""
        from axm_audit.core.rules.quality_rules import DiffSizeRule

        rule = DiffSizeRule()
        assert rule.rule_id == "QUALITY_DIFF_SIZE"

    # -- compute_score curve --

    @pytest.mark.parametrize(
        ("lines", "expected_score"),
        [
            pytest.param(300, 100, id="new_defaults_under_ideal"),
            pytest.param(400, 100, id="boundary_at_ideal"),
            pytest.param(800, 50, id="midrange"),
            pytest.param(1200, 0, id="over_max"),
        ],
    )
    def test_compute_score(self, lines: int, expected_score: int) -> None:
        from axm_audit.core.rules.quality_rules import DiffSizeRule

        assert DiffSizeRule.compute_score(lines) == expected_score


class TestLintingRuleUnit:
    """Pure tests for LintingRule (no I/O)."""

    def test_rule_id_format(self) -> None:
        """Rule ID should be QUALITY_LINT."""

        rule = LintingRule()
        assert rule.rule_id == "QUALITY_LINT"


class TestTypeCheckRuleUnit:
    """Pure tests for TypeCheckRule (no I/O)."""

    def test_rule_id_format(self) -> None:
        """Rule ID should be QUALITY_TYPE."""
        from axm_audit.core.rules.quality_rules import TypeCheckRule

        rule = TypeCheckRule()
        assert rule.rule_id == "QUALITY_TYPE"


class TestParseMypyErrors:
    """Tests for _parse_mypy_errors — non-dict JSON handling.

    Ref: AXM-1220.
    """

    def test_parse_mypy_errors_string_json(self) -> None:
        """String JSON line should be skipped, returns (0, [])."""
        from axm_audit.core.rules.quality_rules import TypeCheckRule

        stdout = '"some status string"\n'
        count, errors = TypeCheckRule.parse_mypy_errors(stdout)
        assert count == 0
        assert errors == []

    def test_parse_mypy_errors_list_json(self) -> None:
        """List JSON line should be skipped, returns (0, [])."""
        from axm_audit.core.rules.quality_rules import TypeCheckRule

        stdout = '["a", "b"]\n'
        count, errors = TypeCheckRule.parse_mypy_errors(stdout)
        assert count == 0
        assert errors == []

    def test_parse_mypy_errors_valid_error(self) -> None:
        """Valid mypy error JSON dict should be parsed correctly."""

        from axm_audit.core.rules.quality_rules import TypeCheckRule

        entry = {
            "severity": "error",
            "file": "src/main.py",
            "line": 10,
            "message": "Incompatible return type",
            "code": "return-value",
        }
        stdout = json.dumps(entry) + "\n"
        count, errors = TypeCheckRule.parse_mypy_errors(stdout)
        assert count == 1
        assert len(errors) == 1
        assert errors[0]["file"] == "src/main.py"
        assert errors[0]["line"] == 10
        assert errors[0]["message"] == "Incompatible return type"
        assert errors[0]["code"] == "return-value"

    def test_parse_mypy_errors_mixed(self) -> None:
        """Mixed stdout: skips string line, parses valid error."""

        from axm_audit.core.rules.quality_rules import TypeCheckRule

        error_entry = {
            "severity": "error",
            "file": "src/bad.py",
            "line": 5,
            "message": "Type mismatch",
            "code": "assignment",
        }
        stdout = '"some status string"\n' + json.dumps(error_entry) + "\n"
        count, errors = TypeCheckRule.parse_mypy_errors(stdout)
        assert count == 1
        assert len(errors) == 1
        assert errors[0]["file"] == "src/bad.py"

    def test_parse_mypy_errors_empty_stdout(self) -> None:
        """Empty stdout returns (0, [])."""
        from axm_audit.core.rules.quality_rules import TypeCheckRule

        count, errors = TypeCheckRule.parse_mypy_errors("")
        assert count == 0
        assert errors == []

    @pytest.mark.parametrize(
        "stdout",
        [
            pytest.param("42\n", id="integer"),
            pytest.param("null\n", id="null"),
            pytest.param("true\n", id="boolean"),
            pytest.param('"plain string"\n', id="string"),
            pytest.param("[1, 2, 3]\n", id="array"),
        ],
    )
    def test_parse_mypy_errors_skips_non_dict_json(self, stdout: str) -> None:
        """Non-dict JSON scalars on a line should be skipped."""
        from axm_audit.core.rules.quality_rules import TypeCheckRule

        count, errors = TypeCheckRule.parse_mypy_errors(stdout)
        assert count == 0
        assert errors == []


class TestDetectEnvIncompleteness:
    """Pure tests for env-incompleteness detection (no I/O).

    Ref: AXM-1900 — audit type must fail loud on missing stubs /
    unfollowed imports / blocking mypy exits, never silently score 100.
    """

    def test_missing_stub_note_is_a_failure(self) -> None:
        """AC1: a 'Library stubs not installed' signal yields a diagnostic
        naming the offending lib and the remediation."""
        from axm_audit.core.rules.quality_rules import detect_env_incompleteness

        stdout = json.dumps(
            {
                "severity": "error",
                "file": "src/mod.py",
                "line": 1,
                "message": 'Library stubs not installed for "jsonschema"',
                "code": "import-untyped",
            }
        )
        diagnostic = detect_env_incompleteness(stdout, 1)
        assert diagnostic is not None
        assert "jsonschema" in diagnostic
        lower = diagnostic.lower()
        assert "stub" in lower or "uv sync" in lower or "install" in lower

    def test_import_untyped_is_a_failure(self) -> None:
        """AC1: an [import-untyped] error is an env-incompleteness signal."""
        from axm_audit.core.rules.quality_rules import detect_env_incompleteness

        stdout = json.dumps(
            {
                "severity": "error",
                "file": "src/mod.py",
                "line": 2,
                "message": 'Skipping analyzing "foo": module is installed, but '
                "missing library stubs or py.typed marker",
                "code": "import-untyped",
            }
        )
        diagnostic = detect_env_incompleteness(stdout, 1)
        assert diagnostic is not None
        assert "foo" in diagnostic
        assert "environment" in diagnostic.lower()

    def test_import_not_found_is_a_failure(self) -> None:
        """AC1: an [import-not-found] error (module truly missing) is an
        env-incompleteness signal."""
        from axm_audit.core.rules.quality_rules import detect_env_incompleteness

        stdout = json.dumps(
            {
                "severity": "error",
                "file": "src/mod.py",
                "line": 1,
                "message": "Cannot find implementation or library stub for "
                'module named "axm_protocols"',
                "code": "import-not-found",
            }
        )
        diagnostic = detect_env_incompleteness(stdout, 1)
        assert diagnostic is not None
        assert "axm_protocols" in diagnostic

    def test_exit_code_2_is_a_failure(self) -> None:
        """AC2: a blocking mypy exit (code 2) is never a pass, even when
        stdout has no parseable JSON error."""
        from axm_audit.core.rules.quality_rules import detect_env_incompleteness

        # Blocking errors are emitted as plain (non-JSON) text.
        stdout = "src/broken.py:1: error: unexpected EOF while parsing  [syntax]\n"
        diagnostic = detect_env_incompleteness(stdout, 2)
        assert diagnostic is not None
        assert "exit code 2" in diagnostic
        assert "unreliable" in diagnostic.lower()

    def test_clean_run_scores_100(self) -> None:
        """AC4: a genuinely clean run (exit 0, no stub/import signals) has
        no env-incompleteness — returns None."""
        from axm_audit.core.rules.quality_rules import detect_env_incompleteness

        assert detect_env_incompleteness("", 0) is None

    def test_plain_type_error_is_not_env_incomplete(self) -> None:
        """AC4 guard: a real type error (exit 1, no stub/import codes) is a
        code problem, not an env problem — returns None so normal scoring
        applies."""
        from axm_audit.core.rules.quality_rules import detect_env_incompleteness

        stdout = json.dumps(
            {
                "severity": "error",
                "file": "src/mod.py",
                "line": 3,
                "message": "Incompatible return value type",
                "code": "return-value",
            }
        )
        assert detect_env_incompleteness(stdout, 1) is None


MODULE = "axm_audit.core.rules.quality_rules"


@pytest.fixture()
def rule() -> FormattingRule:
    return FormattingRule()


@pytest.fixture()
def _bypass_early(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub check_src, _get_audit_targets, and run_in_project."""
    monkeypatch.setattr(f"{MODULE}.FormattingRule.check_src", lambda self, p: None)
    monkeypatch.setattr(
        f"{MODULE}._get_audit_targets",
        lambda p: (["src/"], "src/"),
    )
    monkeypatch.setattr(
        f"{MODULE}.run_in_project",
        lambda *a, **kw: MagicMock(stdout="", returncode=0),
    )


def _patch_unformatted(monkeypatch: pytest.MonkeyPatch, files: list[str]) -> None:
    monkeypatch.setattr(
        f"{MODULE}.FormattingRule._parse_unformatted_files",
        lambda self, result: files,
    )


@pytest.mark.usefixtures("_bypass_early")
@pytest.mark.parametrize(
    ("files", "expected_text"),
    [
        pytest.param(
            ["src/a.py", "src/b.py", "src/c.py"],
            "src/a.py\nsrc/b.py\nsrc/c.py",
            id="bare_paths_multi_file",
        ),
        pytest.param(
            ["src/only.py"],
            "src/only.py",
            id="single_file_no_trailing_newline",
        ),
    ],
)
def test_formatting_text_renders_bare_paths(
    rule: FormattingRule,
    monkeypatch: pytest.MonkeyPatch,
    files: list[str],
    expected_text: str,
) -> None:
    """text= = bare file paths joined by newlines (no bullets, no trailing nl)."""
    _patch_unformatted(monkeypatch, files)
    result = rule.check(Path("/fake"))
    assert result.text == expected_text


@pytest.mark.usefixtures("_bypass_early")
def test_formatting_text_none_on_pass(
    rule: FormattingRule, monkeypatch: pytest.MonkeyPatch
) -> None:
    """text= must be None when no unformatted files."""
    _patch_unformatted(monkeypatch, [])
    result = rule.check(Path("/fake"))
    assert result.text is None


@pytest.mark.usefixtures("_bypass_early")
def test_formatting_text_cap_at_20(
    rule: FormattingRule, monkeypatch: pytest.MonkeyPatch
) -> None:
    """text= must contain at most 20 lines, no trailing newline."""
    files = [f"src/file_{i}.py" for i in range(30)]
    _patch_unformatted(monkeypatch, files)
    result = rule.check(Path("/fake"))
    assert result.text is not None
    lines = result.text.split("\n")
    assert len(lines) == 20
    assert not result.text.endswith("\n")


# ---------------------------------------------------------------------------
# Merged from tests/unit/core/rules/test_formatting.py
# ---------------------------------------------------------------------------


class TestFormattingRule:
    """Pure unit tests for FormattingRule rule_id."""

    def test_rule_id_format(self) -> None:
        """Rule ID should be QUALITY_FORMAT."""
        assert FormattingRule().rule_id == "QUALITY_FORMAT"


# ---------------------------------------------------------------------------
# Merged from tests/unit/core/rules/test_quality_read_diff_config.py
# AC4: read_diff_config promoted to public; _get_audit_targets stays private.
# ---------------------------------------------------------------------------


def test_read_diff_config_public() -> None:
    """read_diff_config is importable as a public callable."""
    from axm_audit.core.rules.quality_rules import read_diff_config

    assert callable(read_diff_config)


@pytest.mark.parametrize(
    ("attr", "reason"),
    [
        pytest.param(
            "_read_diff_config",
            "deprecated private alias _read_diff_config still exposed",
            id="private_alias_removed",
        ),
        pytest.param(
            "get_audit_targets",
            "_get_audit_targets must remain private"
            " (drives only one rule, no test usage)",
            id="get_audit_targets_remains_private",
        ),
    ],
)
def test_quality_module_attribute_absent(attr: str, reason: str) -> None:
    """AC4 surface: certain attributes must NOT be exposed on the quality module."""
    from axm_audit.core.rules import quality_rules

    assert not hasattr(quality_rules, attr), reason


class TestOtherRulesTextRendering:
    def test_format_check_details_adds_indent(self):
        """Rendered failure details from check.text are 5-space indented."""
        from axm_audit.formatters import format_report
        from axm_audit.models import AuditResult, Severity

        check = CheckResult(
            rule_id="OTHER_RULE",
            passed=False,
            message="Some issue",
            severity=Severity.WARNING,
            details={},
            text="line one\nline two",
        )
        report = format_report(AuditResult(checks=[check]))
        assert "     line one" in report
        assert "     line two" in report


# ---------------------------------------------------------------------------
# AXM-1958: LintingRule must fail loud on subprocess env-failure / timeout,
# never report a green 100 off empty stdout.
# ---------------------------------------------------------------------------


@pytest.fixture
def _lint_project(tmp_path: Path) -> Path:
    """A minimal project tree with src/ so LintingRule.check_src passes."""
    (tmp_path / "src" / "pkg").mkdir(parents=True)
    (tmp_path / "src" / "pkg" / "__init__.py").write_text("")
    return tmp_path


def test_lint_timeout_fails_loud_not_green(
    _lint_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC1: a lint subprocess timeout (rc=124, empty stdout) fails loud."""
    import subprocess

    from axm_audit.models import Severity

    def _timed_out(*_a: object, **_kw: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=["ruff"], returncode=124, stdout="", stderr="timed out"
        )

    monkeypatch.setattr(f"{MODULE}.run_in_project", _timed_out)

    result = LintingRule().check(_lint_project)

    assert result.passed is False
    assert result.severity is Severity.ERROR
    assert result.score != 100


def test_lint_expected_exit_with_findings_scores_normally(
    _lint_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC4: a real ruff exit (rc=1) with N findings is scored normally."""
    import subprocess

    findings = [
        {
            "filename": "src/pkg/a.py",
            "location": {"row": 1},
            "code": "E501",
            "message": "line too long",
        },
        {
            "filename": "src/pkg/b.py",
            "location": {"row": 2},
            "code": "F401",
            "message": "unused import",
        },
    ]

    def _ruff_findings(*_a: object, **_kw: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=["ruff"], returncode=1, stdout=json.dumps(findings)
        )

    monkeypatch.setattr(f"{MODULE}.run_in_project", _ruff_findings)

    result = LintingRule().check(_lint_project)

    assert result.score == max(0, 100 - len(findings) * 2)
    assert result.details is not None
    assert result.details["issue_count"] == len(findings)
