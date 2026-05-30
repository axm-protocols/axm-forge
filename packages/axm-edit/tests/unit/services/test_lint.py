"""Tests for services/lint: edit parsing/fabrication and claude subprocess auto-fix."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from axm_edit.services.lint import claude_fix, fabricates_definition, parse_edits

# ---------------------------------------------------------------------------
# Unit tests — parse_edits
# ---------------------------------------------------------------------------


class TestParseEdits:
    """parse_edits maps raw output to a list of old/new pairs."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            pytest.param(
                '[{"old": "x = 1", "new": "_ = 1"}]',
                [{"old": "x = 1", "new": "_ = 1"}],
                id="valid_json",
            ),
            pytest.param("not json at all", [], id="invalid_json"),
            pytest.param('[{"old": "x"}]', [], id="missing_keys"),
            pytest.param(
                '```json\n[{"old":"a","new":"b"}]\n```',
                [{"old": "a", "new": "b"}],
                id="strips_fences",
            ),
        ],
    )
    def test_parse_edits(self, raw: str, expected: list[dict[str, str]]) -> None:
        assert parse_edits(raw) == expected


class TestClaudeWrapsInMarkdown:
    """Output starts with ```json -> stripped before parsing."""

    def test_markdown_fences_stripped(self) -> None:
        raw = '```json\n[{"old": "x", "new": "y"}]\n```'
        result = parse_edits(raw)
        assert len(result) == 1
        assert result[0] == {"old": "x", "new": "y"}


class TestFabricatesDefinition:
    """Detect edits that fabricate a new ``def`` or ``class`` to silence F821/F822."""

    @pytest.mark.parametrize(
        ("edit", "expected"),
        [
            pytest.param(
                {
                    "old": "x = render(items)",
                    "new": "def render(items):\n    return ''\n\nx = render(items)",
                },
                True,
                id="def_detected",
            ),
            pytest.param(
                {"old": "result = fetch()", "new": "async def fetch():\n    ...\n"},
                True,
                id="async_def_detected",
            ),
            pytest.param(
                {"old": "obj = Foo()", "new": "class Foo:\n    pass\n\nobj = Foo()"},
                True,
                id="class_detected",
            ),
            pytest.param(
                {"old": "_render(items)", "new": "render(items)"},
                False,
                id="rename_call_site_not_flagged",
            ),
            pytest.param(
                {"old": "def _render(items):", "new": "def render(items):"},
                False,
                id="rename_def_in_place_not_flagged",
            ),
            pytest.param(
                {"old": '    "_render",\n', "new": ""},
                False,
                id="remove_stale_all_entry_not_flagged",
            ),
        ],
    )
    def test_fabrication_verdict(self, edit: dict[str, str], expected: bool) -> None:
        assert fabricates_definition(edit) is expected


# ---------------------------------------------------------------------------
# Fixtures — claude_fix
# ---------------------------------------------------------------------------


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """Minimal project with a Python file containing an unfixable ruff error."""
    src = tmp_path / "app.py"
    src.write_text("try:\n    x = 1\nexcept:\n    pass\n")
    return tmp_path


def _make_errors(file: str, codes: list[str], *, line: int = 1) -> list[str]:
    """Build ruff-style error strings."""
    return [f"{file}:{line}:{1}: {code} Some error description" for code in codes]


def _claude_completed(stdout: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")


class TestClaudeFixAppliesCorrection:
    """Mock claude returning JSON edits -> file content updated."""

    def test_line_level_fix_applied(
        self,
        project: Path,
        mocker: Any,
    ) -> None:
        # Claude returns JSON old/new edits
        fixed_output = json.dumps([{"old": "except:", "new": "except Exception:"}])

        mocker.patch(
            "axm_edit.services.lint.subprocess.run",
            return_value=_claude_completed(fixed_output),
        )

        errors = _make_errors("app.py", ["E722"], line=3)
        claude_fix(project, errors)

        content = (project / "app.py").read_text()
        assert "except Exception:" in content, "Claude fix should be applied"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestClaudeReturnsGarbage:
    """Non-parseable output -> original code unchanged, errors returned."""

    def test_garbage_output(
        self,
        project: Path,
        mocker: Any,
    ) -> None:
        original_content = (project / "app.py").read_text()

        mocker.patch(
            "axm_edit.services.lint.subprocess.run",
            return_value=subprocess.CompletedProcess(
                args=[],
                returncode=1,
                stdout="<garbage>\x00\xff not valid python",
                stderr="error occurred",
            ),
        )

        errors = _make_errors("app.py", ["E722"])
        remaining = claude_fix(project, errors)

        assert (project / "app.py").read_text() == original_content
        assert remaining, "Should return original errors when claude output is garbage"


class TestClaudeNotInPath:
    """`FileNotFoundError` on subprocess -> skip claude fix, return ruff errors."""

    def test_file_not_found(
        self,
        project: Path,
        mocker: Any,
    ) -> None:
        original_content = (project / "app.py").read_text()

        mocker.patch(
            "axm_edit.services.lint.subprocess.run",
            side_effect=FileNotFoundError("claude: command not found"),
        )

        errors = _make_errors("app.py", ["E722"])
        remaining = claude_fix(project, errors)

        assert (project / "app.py").read_text() == original_content
        assert remaining == errors, "Should return original errors"


class TestClaudeSubprocessTimeout:
    """Claude subprocess hangs -> kill after timeout, return original errors."""

    def test_timeout_handled(
        self,
        project: Path,
        mocker: Any,
    ) -> None:
        original_content = (project / "app.py").read_text()

        mocker.patch(
            "axm_edit.services.lint.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="claude", timeout=60),
        )

        errors = _make_errors("app.py", ["E722"])
        remaining = claude_fix(project, errors)

        assert (project / "app.py").read_text() == original_content
        assert remaining, "Should return original errors on timeout"


class TestClaudeUnparseableOutput:
    """Claude returns non-JSON text -> no changes, errors returned."""

    def test_unparseable_format(
        self,
        project: Path,
        mocker: Any,
    ) -> None:
        original_content = (project / "app.py").read_text()

        mocker.patch(
            "axm_edit.services.lint.subprocess.run",
            return_value=_claude_completed(
                "Here is the fix:\nexcept Exception:\n    pass\n"
            ),
        )

        errors = _make_errors("app.py", ["E722"])
        remaining = claude_fix(project, errors)

        assert (project / "app.py").read_text() == original_content
        assert remaining == errors, (
            "Should return original errors when output is not valid JSON"
        )
