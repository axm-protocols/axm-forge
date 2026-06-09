"""Tests for services/lint: edit parsing/fabrication and harness auto-fix."""

from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from axm_harness.core.errors import HarnessSDKError, MissingCredentialsError

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
# Edge cases
# ---------------------------------------------------------------------------


class TestHarnessReturnsGarbage:
    """Non-parseable output -> original code unchanged, errors returned."""

    def test_garbage_output(
        self,
        project: Path,
        mocker: Any,
    ) -> None:
        original_content = (project / "app.py").read_text()

        mocker.patch(
            "axm_edit.services.lint.run",
            side_effect=_async_run_returning("<garbage>\x00\xff not valid python"),
        )

        errors = _make_errors("app.py", ["E722"])
        remaining = harness_fix(project, errors)

        assert (project / "app.py").read_text() == original_content
        assert remaining, "Should return original errors when output is garbage"


class TestHarnessSDKErrorSkips:
    """`HarnessSDKError` from run() -> skip harness fix, return ruff errors."""

    def test_file_not_found(
        self,
        project: Path,
        mocker: Any,
    ) -> None:
        original_content = (project / "app.py").read_text()

        async def _run(
            adapter: Any, prompt: str, options: Any = None
        ) -> SimpleNamespace:
            raise HarnessSDKError("codex sdk unavailable")

        mocker.patch("axm_edit.services.lint.run", side_effect=_run)

        errors = _make_errors("app.py", ["E722"])
        remaining = harness_fix(project, errors)

        assert (project / "app.py").read_text() == original_content
        assert remaining == errors, "Should return original errors"


class TestHarnessTimeout:
    """Harness run hangs -> cancelled after timeout, original errors returned."""

    def test_timeout_handled(
        self,
        project: Path,
        monkeypatch: pytest.MonkeyPatch,
        mocker: Any,
    ) -> None:
        original_content = (project / "app.py").read_text()
        monkeypatch.setattr("axm_edit.services.lint._FIX_TIMEOUT", 0.05)

        async def _slow(
            adapter: Any, prompt: str, options: Any = None
        ) -> SimpleNamespace:
            await asyncio.sleep(1)
            return _harness_run("[]")

        mocker.patch("axm_edit.services.lint.run", side_effect=_slow)

        errors = _make_errors("app.py", ["E722"])
        remaining = harness_fix(project, errors)

        assert (project / "app.py").read_text() == original_content
        assert remaining, "Should return original errors on timeout"


class TestHarnessUnparseableOutput:
    """Harness returns non-JSON text -> no changes, errors returned."""

    def test_unparseable_format(
        self,
        project: Path,
        mocker: Any,
    ) -> None:
        original_content = (project / "app.py").read_text()

        mocker.patch(
            "axm_edit.services.lint.run",
            side_effect=_async_run_returning(
                "Here is the fix:\nexcept Exception:\n    pass\n"
            ),
        )

        errors = _make_errors("app.py", ["E722"])
        remaining = harness_fix(project, errors)

        assert (project / "app.py").read_text() == original_content
        assert remaining == errors, (
            "Should return original errors when output is not valid JSON"
        )


# ---------------------------------------------------------------------------
# harness_fix — adapter selection and run options (AXM-1866)
# ---------------------------------------------------------------------------


def _harness_run(output: str) -> SimpleNamespace:
    """Minimal HarnessRun stub exposing the ``output`` field."""
    return SimpleNamespace(output=output)


def _adapter_names(mock_get: Any) -> list[Any]:
    """Adapter names passed to get_adapter, positional or keyword."""
    return [
        call.args[0] if call.args else call.kwargs.get("name")
        for call in mock_get.call_args_list
    ]


def _async_run_returning(output: str) -> Any:
    """Async stand-in for the harness ``run`` returning *output*."""

    async def _run(adapter: Any, prompt: str, options: Any = None) -> SimpleNamespace:
        return _harness_run(output)

    return _run


class TestHarnessAdapterSelection:
    """AC2: env var selection, codex->claude fallback, graceful skip."""

    def test_adapter_env_var_selects_claude(
        self,
        project: Path,
        monkeypatch: pytest.MonkeyPatch,
        mocker: Any,
    ) -> None:
        """AC2: AXM_EDIT_FIX_ADAPTER=claude-agent-sdk selects that adapter."""
        monkeypatch.setenv("AXM_EDIT_FIX_ADAPTER", "claude-agent-sdk")
        mock_get = mocker.patch(
            "axm_edit.services.lint.get_adapter",
            return_value=mocker.Mock(),
        )

        async def _run(
            adapter: Any, prompt: str, options: Any = None
        ) -> SimpleNamespace:
            return _harness_run("[]")

        mocker.patch("axm_edit.services.lint.run", side_effect=_run)

        harness_fix(project, _make_errors("app.py", ["E722"], line=3))

        names = _adapter_names(mock_get)
        assert "claude-agent-sdk" in names
        assert "codex-sdk" not in names

    def test_codex_missing_credentials_falls_back_to_claude(
        self,
        project: Path,
        monkeypatch: pytest.MonkeyPatch,
        mocker: Any,
    ) -> None:
        """AC2: MissingCredentialsError on codex-sdk -> claude-agent-sdk fallback."""
        monkeypatch.delenv("AXM_EDIT_FIX_ADAPTER", raising=False)
        fallback_adapter = mocker.Mock()

        def _get(name: str, *args: Any, **kwargs: Any) -> Any:
            if name == "codex-sdk":
                raise MissingCredentialsError("codex credentials missing")
            return fallback_adapter

        mock_get = mocker.patch("axm_edit.services.lint.get_adapter", side_effect=_get)
        run_prompts: list[str] = []

        async def _run(
            adapter: Any, prompt: str, options: Any = None
        ) -> SimpleNamespace:
            run_prompts.append(prompt)
            return _harness_run("[]")

        mocker.patch("axm_edit.services.lint.run", side_effect=_run)

        harness_fix(project, _make_errors("app.py", ["E722"], line=3))

        names = _adapter_names(mock_get)
        assert names[0] == "codex-sdk"
        assert "claude-agent-sdk" in names
        assert run_prompts, "fix should be attempted via the fallback adapter"

    def test_no_adapter_available_skips_with_warning(
        self,
        project: Path,
        monkeypatch: pytest.MonkeyPatch,
        mocker: Any,
    ) -> None:
        """AC2: no adapter available -> errors unchanged + skip warning."""
        monkeypatch.delenv("AXM_EDIT_FIX_ADAPTER", raising=False)
        mocker.patch(
            "axm_edit.services.lint.get_adapter",
            side_effect=MissingCredentialsError("no harness sdk available"),
        )
        original_content = (project / "app.py").read_text()

        errors = _make_errors("app.py", ["E722"], line=3)
        warnings: list[str] = []
        remaining = harness_fix(project, errors, warnings=warnings)

        assert remaining == errors
        assert (project / "app.py").read_text() == original_content
        assert any("no harness available, auto-fix skipped" in w for w in warnings)


class TestHarnessModelOption:
    """AC3: AXM_EDIT_FIX_MODEL env var overrides the run() model option."""

    def test_model_env_var_in_options(
        self,
        project: Path,
        monkeypatch: pytest.MonkeyPatch,
        mocker: Any,
    ) -> None:
        """AC3: AXM_EDIT_FIX_MODEL lands in run() options['model']."""
        monkeypatch.setenv("AXM_EDIT_FIX_MODEL", "gpt-5-codex")
        mocker.patch("axm_edit.services.lint.get_adapter", return_value=mocker.Mock())
        captured: dict[str, Any] = {}

        async def _run(
            adapter: Any, prompt: str, options: Any = None
        ) -> SimpleNamespace:
            captured.update(options or {})
            return _harness_run("[]")

        mocker.patch("axm_edit.services.lint.run", side_effect=_run)

        harness_fix(project, _make_errors("app.py", ["E722"], line=3))

        assert captured.get("model") == "gpt-5-codex"
