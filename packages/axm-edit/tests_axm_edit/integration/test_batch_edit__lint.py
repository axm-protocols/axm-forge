"""Integration tests for batch_edit's per-root ruff-availability gate.

``BatchEditTool`` no longer probes a global-``PATH`` ruff via the private
``_has_ruff``; it delegates to the public
:func:`axm_edit.services.lint.ruff_available`, imported directly into
``axm_edit.tools.batch_edit`` and called with the *target root* it edits.
These tests exercise the two branches end-to-end against a real project on
disk: available → the lint pass runs; unavailable → a clean skip with no
crash surfaced.
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Any

import pytest

from axm_edit.tools.batch_edit import BatchEditTool


@pytest.fixture(autouse=True)
def _no_global_ruff_stub() -> None:
    """Drop the global autouse stub; each test drives the gate explicitly."""
    return None


@pytest.fixture
def tool() -> BatchEditTool:
    return BatchEditTool()


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A minimal on-disk project with one Python file to edit."""
    (tmp_path / "hello.py").write_text("x = 1\n")
    return tmp_path


def _replace_op(file: str, old: str, new: str) -> dict[str, Any]:
    return {"op": "replace", "file": file, "edits": [{"old": old, "new": new}]}


def _ruff_calls(spy: Any) -> list[Any]:
    """Filter a ``subprocess.run`` spy down to the ruff invocations."""
    calls = []
    for call in spy.call_args_list:
        args = call.args[0] if call.args else call.kwargs.get("args", [])
        if isinstance(args, list) and "ruff" in args:
            calls.append(call)
    return calls


@pytest.mark.integration
class TestEnvLocalRuffRunsLint:
    """AC2/AC3: ruff available for the root → the lint pass executes."""

    def test_env_local_ruff_runs_lint(
        self, tool: BatchEditTool, project: Path, mocker: Any
    ) -> None:
        probe = mocker.patch(
            "axm_edit.tools.batch_edit.ruff_available", return_value=True
        )
        run = mocker.patch(
            "axm_edit.tools.batch_edit.subprocess.run",
            return_value=mocker.Mock(returncode=0, stdout=""),
        )

        result = tool.execute(
            path=str(project),
            operations=[_replace_op("hello.py", "x = 1", "x = 2")],
        )

        assert result.success
        # AC2: the availability probe ran against the edited project's root.
        probe.assert_called_once_with(project.resolve())
        # AC3: available → the lint pass ran (ruff was invoked, summary set).
        assert _ruff_calls(run), "ruff should be invoked when available"
        assert result.data is not None
        assert "lint" in result.data


@pytest.mark.integration
class TestNoRuffSkipsLintCleanly:
    """AC3: ruff absent for the root → clean skip, edit still applied."""

    def test_no_ruff_skips_lint_without_crash(
        self, tool: BatchEditTool, project: Path, mocker: Any
    ) -> None:
        probe = mocker.patch(
            "axm_edit.tools.batch_edit.ruff_available", return_value=False
        )
        spy = mocker.patch(
            "axm_edit.tools.batch_edit.subprocess.run",
            wraps=subprocess.run,
        )

        result = tool.execute(
            path=str(project),
            operations=[_replace_op("hello.py", "x = 1", "x = 2")],
        )

        # Edit applied despite ruff being unavailable.
        assert result.success
        assert result.error is None
        assert (project / "hello.py").read_text() == "x = 2\n"
        # Lint pass was skipped: the probe gated it and ruff never ran.
        probe.assert_called_once_with(project.resolve())
        assert not _ruff_calls(spy), "ruff must not run when unavailable"
        # A clean, probe-driven skip — never a false 'ruff crashed'.
        warnings = result.data.get("warnings", []) if result.data else []
        assert not any("ruff crashed" in w for w in warnings)


@pytest.mark.integration
class TestRewrittenFileIsLinted:
    """AC5: a rewritten Python file joins the post-apply lint set."""

    def test_rewritten_file_is_linted_post_apply(
        self, tool: BatchEditTool, project: Path, mocker: Any
    ) -> None:
        """AC5: the rewrite target reaches the ruff pass and a lint report is built."""
        target = project / "hello.py"
        checksum = hashlib.sha256(target.read_bytes()).hexdigest()
        mocker.patch("axm_edit.tools.batch_edit.ruff_available", return_value=True)
        run_ruff = mocker.patch(
            "axm_edit.tools.batch_edit._run_ruff", return_value=([], [])
        )

        result = tool.execute(
            path=str(project),
            operations=[
                {
                    "op": "rewrite",
                    "file": "hello.py",
                    "content": "import os\n\nx = 2\n",
                    "expected_checksum": checksum,
                }
            ],
        )

        assert result.success, result.error
        assert target.read_text() == "import os\n\nx = 2\n"
        assert run_ruff.call_count == 1, run_ruff.call_args_list
        linted = run_ruff.call_args.args[1]
        assert target.resolve() in linted, linted
        assert result.data is not None
        assert "lint" in result.data
