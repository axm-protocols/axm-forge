"""Integration tests for harness-driven lint auto-fix (AXM-1866)."""

from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from axm_edit.services.lint import harness_fix
from tests.integration._helpers import _make_errors

# axm-harness is an optional extra (axm-edit[harness]); the adapter and runner
# are mocked here, so the SDK need not be installed. When it IS installed, the
# real exceptions must be used (lint._harness_error() returns the real
# HarnessSDKError base); the stand-ins only cover environments without it.
try:
    from axm_harness.core.errors import (
        HarnessSDKError,
        MissingCredentialsError,
    )
except ImportError:  # pragma: no cover - exercised only without the extra

    class HarnessSDKError(Exception):  # type: ignore[no-redef]
        """Stand-in for ``axm_harness.core.errors.HarnessSDKError``."""

    class MissingCredentialsError(HarnessSDKError):  # type: ignore[no-redef]
        """Stand-in for ``axm_harness.core.errors.MissingCredentialsError``."""


pytestmark = pytest.mark.integration


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """Minimal project with a Python file containing an unfixable ruff error."""
    src = tmp_path / "app.py"
    src.write_text("try:\n    x = 1\nexcept:\n    pass\n")
    return tmp_path


def _harness_run(output: str) -> SimpleNamespace:
    """Minimal HarnessRun stub exposing the ``output`` field."""
    return SimpleNamespace(output=output)


# ---------------------------------------------------------------------------
# Migrated from ``test_claude_fix.py`` — transport re-targeted to harness
# ---------------------------------------------------------------------------


@pytest.fixture
def multi_file_project(tmp_path: Path) -> Path:
    """Project with unfixable errors across two files."""
    (tmp_path / "file_a.py").write_text(
        "try:\n    a = 1\nexcept:\n    pass\n"
        "try:\n    b = 2\nexcept:\n    pass\n"
        "try:\n    c = 3\nexcept:\n    pass\n"
    )
    (tmp_path / "file_b.py").write_text("try:\n    d = 4\nexcept:\n    pass\n")
    return tmp_path


def _capturing_run(prompts: list[str], output: str = "[]") -> Any:
    """Async harness ``run`` stub appending each prompt to *prompts*."""

    async def _run(adapter: Any, prompt: str, options: Any = None) -> SimpleNamespace:
        prompts.append(prompt)
        return _harness_run(output)

    return _run


class TestHarnessFixPromptContainsErrors:
    """Mock harness -> prompt includes error codes + snippets."""

    def test_prompt_includes_error_code(self, project: Path, mocker: Any) -> None:
        mocker.patch("axm_edit.services.lint.get_adapter", return_value=mocker.Mock())
        prompts: list[str] = []
        mocker.patch("axm_edit.services.lint.run", side_effect=_capturing_run(prompts))

        errors = _make_errors("app.py", ["E722"])
        harness_fix(project, errors)

        assert prompts
        assert "E722" in prompts[0], "Prompt must include the error code"

    def test_prompt_contains_snippets_not_full_file(
        self, project: Path, mocker: Any
    ) -> None:
        # Write a 50-line file — error on line 3
        # 50 < 300 threshold -> full file is now sent (AXM-969)
        lines = [f"line_{i} = {i}" for i in range(50)]
        lines[2] = "try:\n    x = 1\nexcept:\n    pass"
        (project / "app.py").write_text("\n".join(lines) + "\n")

        mocker.patch("axm_edit.services.lint.get_adapter", return_value=mocker.Mock())
        prompts: list[str] = []
        mocker.patch("axm_edit.services.lint.run", side_effect=_capturing_run(prompts))

        errors = _make_errors("app.py", ["E722"], line=3)
        harness_fix(project, errors)

        assert prompts
        prompt = prompts[0]
        # Small file (50 lines < 300): full file content is sent
        assert "line_40" in prompt, (
            "Small file should use full-file prompt (< 300 threshold)"
        )
        assert "line_2" in prompt or "line_1" in prompt, (
            "Prompt should contain nearby context"
        )


class TestHarnessFixMaxOneRetry:
    """Error persists after fix -> returns lint_errors, no second harness call."""

    def test_max_one_retry(self, project: Path, mocker: Any) -> None:
        mocker.patch("axm_edit.services.lint.get_adapter", return_value=mocker.Mock())
        fixed_output = json.dumps([{"old": "except:", "new": "except Exception:"}])
        prompts: list[str] = []
        mocker.patch(
            "axm_edit.services.lint.run",
            side_effect=_capturing_run(prompts, output=fixed_output),
        )

        def _ruff_still_broken(
            cmd: list[str], **kwargs: Any
        ) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=1,
                stdout="app.py:3:1: E722 Still broken\n",
                stderr="",
            )

        mocker.patch(
            "axm_edit.services.lint.subprocess.run",
            side_effect=_ruff_still_broken,
        )

        errors = _make_errors("app.py", ["E722"], line=3)
        remaining = harness_fix(project, errors)

        assert remaining, "Should return remaining errors when ruff re-check fails"
        assert len(prompts) == 1, "Harness must be called at most once per file"


class TestHarnessFixGroupsByFile:
    """3 errors in file A, 1 in file B -> 2 harness calls."""

    def test_groups_by_file(self, multi_file_project: Path, mocker: Any) -> None:
        mocker.patch("axm_edit.services.lint.get_adapter", return_value=mocker.Mock())
        prompts: list[str] = []
        mocker.patch("axm_edit.services.lint.run", side_effect=_capturing_run(prompts))

        errors = [
            *_make_errors("file_a.py", ["E722", "E722", "E722"]),
            *_make_errors("file_b.py", ["E722"]),
        ]
        harness_fix(multi_file_project, errors)

        assert len(prompts) == 2, "Should run one harness call per file"


class TestHarnessFixRuffRecheck:
    """AC6: ruff re-check runs after the harness fix is applied."""

    def test_ruff_recheck_after_fix(self, project: Path, mocker: Any) -> None:
        mocker.patch("axm_edit.services.lint.get_adapter", return_value=mocker.Mock())
        fixed_output = json.dumps([{"old": "except:", "new": "except Exception:"}])
        call_order: list[str] = []

        async def _run(
            adapter: Any, prompt: str, options: Any = None
        ) -> SimpleNamespace:
            call_order.append("harness")
            return _harness_run(fixed_output)

        mocker.patch("axm_edit.services.lint.run", side_effect=_run)

        def _ruff(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
            call_order.append("ruff")
            return subprocess.CompletedProcess(
                args=cmd, returncode=0, stdout="", stderr=""
            )

        mocker.patch("axm_edit.services.lint.subprocess.run", side_effect=_ruff)

        errors = _make_errors("app.py", ["E722"], line=3)
        harness_fix(project, errors)

        assert call_order == ["harness", "ruff"], (
            "Ruff re-check must run after the harness fix"
        )


class TestEmptyRemainingErrors:
    """ruff --fix solved everything -> no harness call made."""

    def test_no_subprocess_on_empty(self, project: Path, mocker: Any) -> None:
        mock_get = mocker.patch(
            "axm_edit.services.lint.get_adapter", return_value=mocker.Mock()
        )
        mock_run = mocker.patch(
            "axm_edit.services.lint.run", side_effect=_capturing_run([])
        )

        remaining = harness_fix(project, [])

        assert remaining == []
        mock_get.assert_not_called()
        mock_run.assert_not_called()


class TestNoHarnessSkipsAutofix:
    """AC2: if no adapter resolves, harness auto-fix step silently skipped."""

    def test_no_harness_skips_autofix(
        self,
        project: Path,
        mocker: Any,
    ) -> None:
        mocker.patch(
            "axm_edit.services.lint.get_adapter",
            side_effect=MissingCredentialsError("no harness sdk available"),
        )
        run_spy = mocker.patch(
            "axm_edit.services.lint.run", side_effect=_capturing_run([])
        )

        errors = _make_errors("app.py", ["E722"])
        warnings: list[str] = []
        remaining = harness_fix(project, errors, warnings=warnings)

        # Errors returned as-is, no harness call
        assert remaining == errors
        assert any("no harness available" in w for w in warnings)
        run_spy.assert_not_called()


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
