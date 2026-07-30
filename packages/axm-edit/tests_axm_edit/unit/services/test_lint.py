"""Unit tests for ruff diagnostic filtering + availability probing."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from axm_edit.services.lint import filter_ruff_lines, ruff_available


@pytest.fixture(autouse=True)
def _assume_tools_available() -> None:
    """Override the global conftest stub so the real probe runs here."""
    return None


class TestFilterRuffLines:
    """filter_ruff_lines keeps diagnostics and drops ruff summary noise."""

    def test_keeps_diagnostic_lines(self) -> None:
        stdout = "app.py:1:1: F401 unused import\napp.py:2:1: E722 bare except\n"
        assert filter_ruff_lines(stdout) == [
            "app.py:1:1: F401 unused import",
            "app.py:2:1: E722 bare except",
        ]

    def test_drops_summary_noise(self) -> None:
        stdout = (
            "app.py:1:1: F401 unused import\n"
            "Found 1 error.\n"
            "[*] 1 fixable with the `--fix` option.\n"
            "No fixes available.\n"
        )
        assert filter_ruff_lines(stdout) == ["app.py:1:1: F401 unused import"]

    def test_drops_blank_lines(self) -> None:
        stdout = "\napp.py:1:1: F401 unused\n\n   \n"
        assert filter_ruff_lines(stdout) == ["app.py:1:1: F401 unused"]

    def test_empty_input_returns_empty(self) -> None:
        assert filter_ruff_lines("") == []


class TestRuffAvailable:
    """ruff_available probes ``uv run ruff --version`` per resolved root."""

    def test_probe_shells_uv_run_ruff_version(
        self, mocker: Any, tmp_path: Path
    ) -> None:
        run = mocker.patch(
            "axm_edit.services.lint.subprocess.run",
            return_value=mocker.Mock(returncode=0),
        )

        assert ruff_available(tmp_path) is True

        run.assert_called_once()
        args, kwargs = run.call_args
        assert args[0] == ["uv", "run", "ruff", "--version"]
        assert kwargs["cwd"] == tmp_path

    def test_memoized_per_root_and_reprobes_new_root(
        self, mocker: Any, tmp_path: Path
    ) -> None:
        run = mocker.patch(
            "axm_edit.services.lint.subprocess.run",
            return_value=mocker.Mock(returncode=0),
        )
        root_a = tmp_path / "a"
        root_a.mkdir()
        root_b = tmp_path / "b"
        root_b.mkdir()

        ruff_available(root_a)
        ruff_available(root_a)
        assert run.call_count == 1  # second call for same root hits the cache

        ruff_available(root_b)
        assert run.call_count == 2  # a distinct root re-probes

    def test_missing_ruff_returns_false(self, mocker: Any, tmp_path: Path) -> None:
        mocker.patch(
            "axm_edit.services.lint.subprocess.run",
            return_value=mocker.Mock(returncode=1),
        )

        assert ruff_available(tmp_path) is False

    def test_absent_binary_returns_false_without_raising(
        self, mocker: Any, tmp_path: Path
    ) -> None:
        mocker.patch(
            "axm_edit.services.lint.subprocess.run",
            side_effect=FileNotFoundError,
        )

        assert ruff_available(tmp_path) is False

    def test_no_import_time_probe(self) -> None:
        import axm_edit.services.lint as lint_mod

        # The old import-time ``shutil.which`` constant is gone: no module-level
        # ``_has_ruff`` boolean and no ``shutil`` reference to compute one.
        assert not hasattr(lint_mod, "_has_ruff")
        assert not hasattr(lint_mod, "shutil")
