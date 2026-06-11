"""Tests for services/lint: edit parsing/fabrication and harness auto-fix."""

from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from axm_edit.services.lint import (
    fabricates_definition,
    harness_fix,
    parse_edits,
)

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


class TestHarnessWrapsInMarkdown:
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
# Fixtures — harness_fix
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


def _ruff_clean() -> subprocess.CompletedProcess[str]:
    """CompletedProcess stub for a clean ruff re-check."""
    return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")


class TestHarnessFixAppliesCorrection:
    """Mock harness returning JSON edits -> file content updated."""

    def test_line_level_fix_applied(
        self,
        project: Path,
        mocker: Any,
    ) -> None:
        # Harness returns JSON old/new edits
        fixed_output = json.dumps([{"old": "except:", "new": "except Exception:"}])

        mocker.patch(
            "axm_edit.services.lint.run",
            side_effect=_async_run_returning(fixed_output),
        )
        mocker.patch(
            "axm_edit.services.lint.subprocess.run",
            return_value=_ruff_clean(),
        )

        errors = _make_errors("app.py", ["E722"], line=3)
        harness_fix(project, errors)

        content = (project / "app.py").read_text()
        assert "except Exception:" in content, "Harness fix should be applied"


# ---------------------------------------------------------------------------
# harness_fix — adapter selection and run options (AXM-1866)
# ---------------------------------------------------------------------------


def _harness_run(output: str) -> SimpleNamespace:
    """Minimal HarnessRun stub exposing the ``output`` field."""
    return SimpleNamespace(output=output)


def _async_run_returning(output: str) -> Any:
    """Async stand-in for the harness ``run`` returning *output*."""

    async def _run(adapter: Any, prompt: str, options: Any = None) -> SimpleNamespace:
        return _harness_run(output)

    return _run


class TestFixAppliedFromHarnessOutput:
    """AC1, AC6: valid harness edits rewrite the file and pass ruff re-check."""

    def test_fix_applied_from_harness_output(self, project: Path, mocker: Any) -> None:
        """AC1, AC6: file rewritten, ruff re-check runs, fixed errors dropped."""
        mocker.patch("axm_edit.services.lint.get_adapter", return_value=mocker.Mock())
        fixed_output = json.dumps([{"old": "except:", "new": "except Exception:"}])

        async def _run(
            adapter: Any, prompt: str, options: Any = None
        ) -> SimpleNamespace:
            return _harness_run(fixed_output)

        mocker.patch("axm_edit.services.lint.run", side_effect=_run)

        ruff_calls: list[list[str]] = []

        def _ruff(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
            ruff_calls.append(cmd)
            return subprocess.CompletedProcess(
                args=cmd, returncode=0, stdout="", stderr=""
            )

        mocker.patch("axm_edit.services.lint.subprocess.run", side_effect=_ruff)

        errors = _make_errors("app.py", ["E722"], line=3)
        remaining = harness_fix(project, errors)

        assert "except Exception:" in (project / "app.py").read_text()
        assert ruff_calls, "ruff re-check should run after a harness fix"
        assert remaining == [], "fixed errors must be absent from the return"


class TestTimeoutReturnsOriginalErrors:
    """AC4: run() exceeding the timeout returns the original errors."""

    def test_timeout_returns_original_errors(
        self,
        project: Path,
        monkeypatch: pytest.MonkeyPatch,
        mocker: Any,
    ) -> None:
        """AC4: wait_for timeout -> warning + original errors returned."""
        mocker.patch("axm_edit.services.lint.get_adapter", return_value=mocker.Mock())
        monkeypatch.setattr("axm_edit.services.lint._FIX_TIMEOUT", 0.05)
        original_content = (project / "app.py").read_text()

        async def _slow(
            adapter: Any, prompt: str, options: Any = None
        ) -> SimpleNamespace:
            await asyncio.sleep(1)
            return _harness_run("[]")

        mocker.patch("axm_edit.services.lint.run", side_effect=_slow)

        errors = _make_errors("app.py", ["E722"], line=3)
        warnings: list[str] = []
        remaining = harness_fix(project, errors, warnings=warnings)

        assert remaining == errors
        assert any("harness timed out fixing app.py" in w for w in warnings)
        assert (project / "app.py").read_text() == original_content
