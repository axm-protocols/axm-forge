from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from axm_audit.hooks.quality_check import QualityCheckHook, _read_snippet

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_py_file(tmp_path: Path) -> Path:
    """Create a 20-line Python file with a known type error at line 10."""
    lines = [f"line_{i} = {i}\n" for i in range(1, 21)]
    # Line 10 has a deliberate "error" we can reference
    lines[9] = "payload = dict(bad_key=True)  # type error\n"
    f = tmp_path / "sample.py"
    f.write_text("".join(lines))
    return f


@pytest.fixture()
def hook() -> QualityCheckHook:
    return QualityCheckHook()


# ---------------------------------------------------------------------------
# Unit tests — _read_snippet helper
# ---------------------------------------------------------------------------


class TestReadSnippet:
    """Tests for the _read_snippet helper function."""

    def test_snippet_included_in_violation(
        self, tmp_path: Path, sample_py_file: Path
    ) -> None:
        """Snippet is returned with surrounding lines for a valid file/line."""
        result = _read_snippet(tmp_path, "sample.py", 10)
        assert result is not None
        assert "payload" in result

    def test_snippet_marks_violation_line(
        self, tmp_path: Path, sample_py_file: Path
    ) -> None:
        """The violation line is marked with '>' in the snippet."""
        result = _read_snippet(tmp_path, "sample.py", 10)
        assert result is not None
        for line in result.splitlines():
            if "payload" in line:
                assert line.lstrip().startswith("10>")
                break
        else:
            pytest.fail("Violation line not found with '>' marker")

    def test_snippet_has_line_numbers(
        self, tmp_path: Path, sample_py_file: Path
    ) -> None:
        """Each line in the snippet includes a line number prefix (AC4)."""
        result = _read_snippet(tmp_path, "sample.py", 10)
        assert result is not None
        for line in result.splitlines():
            # Each line should start with a number
            stripped = line.lstrip()
            assert stripped[0].isdigit(), f"Missing line number: {line!r}"

    def test_snippet_null_for_empty_file_path(self, tmp_path: Path) -> None:
        """Returns None when file path is empty."""
        result = _read_snippet(tmp_path, "", 10)
        assert result is None

    def test_snippet_null_for_zero_line(
        self, tmp_path: Path, sample_py_file: Path
    ) -> None:
        """Returns None when line number is 0."""
        result = _read_snippet(tmp_path, "sample.py", 0)
        assert result is None

    def test_snippet_null_for_missing_file(self, tmp_path: Path) -> None:
        """Returns None when file does not exist (no crash)."""
        result = _read_snippet(tmp_path, "nonexistent.py", 5)
        assert result is None


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestReadSnippetEdgeCases:
    """Edge-case scenarios for _read_snippet."""

    def test_line_near_start_of_file(self, tmp_path: Path) -> None:
        """Violation at line 2 — snippet starts at line 1, no negative index."""
        content = "\n".join(f"line {i}" for i in range(1, 11))
        (tmp_path / "short.py").write_text(content)
        result = _read_snippet(tmp_path, "short.py", 2)
        assert result is not None
        # First line number in snippet must be 1 (not 0 or negative)
        first_line = result.splitlines()[0].lstrip()
        assert first_line.startswith("1")

    def test_line_near_end_of_file(self, tmp_path: Path) -> None:
        """Violation at last line — snippet ends at EOF, no IndexError."""
        lines = [f"line {i}" for i in range(1, 6)]
        (tmp_path / "tiny.py").write_text("\n".join(lines))
        result = _read_snippet(tmp_path, "tiny.py", 5)
        assert result is not None
        assert "line 5" in result

    def test_binary_unreadable_file(self, tmp_path: Path) -> None:
        """Violation in a binary file — returns None, no crash."""
        binary = tmp_path / "image.bin"
        binary.write_bytes(bytes(range(256)))
        result = _read_snippet(tmp_path, "image.bin", 3)
        assert result is None


# ---------------------------------------------------------------------------
# Integration — snippet field in hook violations
# ---------------------------------------------------------------------------


class TestHookSnippetIntegration:
    """Verify QualityCheckHook.execute populates snippet in violations."""

    def test_violations_contain_snippet_key(
        self,
        hook: QualityCheckHook,
        tmp_path: Path,
        sample_py_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Each violation dict has a 'snippet' key after hook execution."""
        from axm_audit.hooks import quality_check as qc_mod

        fake_violation: dict[str, Any] = {
            "file": "sample.py",
            "line": 10,
            "message": "type error",
            "code": "E001",
        }
        fake_agent_output: dict[str, Any] = {
            "failed": [
                {
                    "rule_id": "R001",
                    "details": {"errors": [fake_violation]},
                }
            ]
        }

        monkeypatch.setattr(
            qc_mod, "audit_project", lambda *a, **kw: MagicMock(checks=[MagicMock()])
        )
        monkeypatch.setattr(qc_mod, "format_agent", lambda _: fake_agent_output)

        result = hook.execute(
            context={"working_dir": str(tmp_path)},
        )
        violations = result.metadata["violations"]
        assert len(violations) >= 1
        assert "snippet" in violations[0]
        # snippet should be a string with content (file exists)
        assert violations[0]["snippet"] is not None
        assert "payload" in violations[0]["snippet"]

    def test_fallback_violation_snippet_is_none(
        self,
        hook: QualityCheckHook,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Fallback violations (no inner errors) have snippet=None (empty file)."""
        from axm_audit.hooks import quality_check as qc_mod

        fake_agent_output: dict[str, Any] = {
            "failed": [
                {
                    "rule_id": "R002",
                    "message": "general failure",
                    "details": {},
                }
            ]
        }

        monkeypatch.setattr(
            qc_mod, "audit_project", lambda *a, **kw: MagicMock(checks=[MagicMock()])
        )
        monkeypatch.setattr(qc_mod, "format_agent", lambda _: fake_agent_output)

        result = hook.execute(
            context={"working_dir": str(tmp_path)},
        )
        violations = result.metadata["violations"]
        assert len(violations) == 1
        assert violations[0]["snippet"] is None
