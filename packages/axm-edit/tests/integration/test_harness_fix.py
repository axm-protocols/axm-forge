"""Integration tests for harness-driven lint auto-fix (AXM-1866)."""

from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from axm_edit.services.lint import build_prompt, harness_fix
from tests.integration._helpers import _make_errors

# axm-harness is an optional extra (axm-edit[harness]); the adapter and runner
# are mocked here, so the SDK need not be installed. When it IS installed, the
# real exception must be used (lint._harness_error() returns the real
# HarnessSDKError base); the stand-in only covers environments without it.
try:
    from axm_harness.core.errors import MissingCredentialsError
except ImportError:  # pragma: no cover - exercised only without the extra

    class MissingCredentialsError(Exception):  # type: ignore[no-redef]
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


class TestOptionsContract:
    """AC1, AC3: run() receives system_prompt, cwd, response_schema, prompt."""

    def test_options_contract(self, project: Path, mocker: Any) -> None:
        """AC1, AC3: options passed to run() carry the full fix contract."""
        mocker.patch("axm_edit.services.lint.get_adapter", return_value=mocker.Mock())
        captured: dict[str, Any] = {}

        async def _run(
            adapter: Any, prompt: str, options: Any = None
        ) -> SimpleNamespace:
            captured["prompt"] = prompt
            captured["options"] = dict(options or {})
            return _harness_run("[]")

        mocker.patch("axm_edit.services.lint.run", side_effect=_run)

        errors = _make_errors("app.py", ["E722"], line=3)
        harness_fix(project, errors)

        options = captured["options"]
        # System prompt carries the anti-fabrication rules
        assert "NEVER create new function" in options["system_prompt"]
        assert options["cwd"] == str(project)
        # response_schema imposes a JSON array of {old, new} objects
        schema_dump = json.dumps(options["response_schema"])
        assert '"old"' in schema_dump
        assert '"new"' in schema_dump
        # Prompt comes from build_prompt
        assert captured["prompt"] == build_prompt(project / "app.py", errors)


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
