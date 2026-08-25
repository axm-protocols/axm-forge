"""Integration tests for BatchEditCheckTool — real filesystem, read-only."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from axm_edit.tools.batch_edit_check import BatchEditCheckTool

pytestmark = pytest.mark.integration

DIAGNOSTIC_KEYS = {"op_index", "file", "severity", "code", "message", "hint"}


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A real on-disk tree with two committed-looking Python modules."""
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "mod.py").write_text("value = 1\n")
    (package / "legacy.py").write_text("legacy = True\n")
    return tmp_path


def _snapshot(root: Path) -> dict[str, tuple[int, str]]:
    """Relative path -> (mtime_ns, sha256) for every entry under *root*."""
    snapshot: dict[str, tuple[int, str]] = {}
    for path in sorted(root.rglob("*")):
        key = str(path.relative_to(root))
        if path.is_file():
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            snapshot[key] = (path.stat().st_mtime_ns, digest)
        else:
            snapshot[key] = (path.stat().st_mtime_ns, "<dir>")
    return snapshot


class TestValidOperationSet:
    """AC1: a sound batch yields an empty diagnostic list."""

    def test_valid_set_produces_no_diagnostic(self, project: Path) -> None:
        """AC1: ok is True and diagnostics is empty on a valid batch."""
        result = BatchEditCheckTool().execute(
            path=str(project),
            operations=[
                {
                    "op": "replace",
                    "file": "pkg/mod.py",
                    "edits": [{"old": "value = 1", "new": "value = 2"}],
                },
                {
                    "op": "create",
                    "file": "pkg/new_mod.py",
                    "content": "value = 3\n",
                },
            ],
        )

        assert result.success is True
        assert result.data is not None
        assert result.data["ok"] is True
        assert result.data["diagnostics"] == []


class TestInvalidOperationSet:
    """AC2: broken operations surface stable codes and a full shape."""

    def test_invalid_set_reports_create_on_existing_and_unknown_edit_key(
        self, project: Path
    ) -> None:
        """AC2: both codes are reported, each diagnostic fully shaped."""
        result = BatchEditCheckTool().execute(
            path=str(project),
            operations=[
                {
                    "op": "create",
                    "file": "pkg/mod.py",
                    "content": "value = 9\n",
                },
                {
                    "op": "replace",
                    "file": "pkg/legacy.py",
                    "edits": [
                        {
                            "old": "legacy = True",
                            "new": "legacy = False",
                            "olds": "typo-key",
                        }
                    ],
                },
            ],
        )

        assert result.success is True
        assert result.data is not None
        assert result.data["ok"] is False
        diagnostics = result.data["diagnostics"]
        codes = {diagnostic["code"] for diagnostic in diagnostics}
        assert "CREATE_ON_EXISTING" in codes
        assert "UNKNOWN_EDIT_KEY" in codes
        for diagnostic in diagnostics:
            assert DIAGNOSTIC_KEYS <= set(diagnostic)


class TestErrorContract:
    """AC3: tool-level failures degrade to ToolResult(success=False)."""

    def test_missing_path_returns_failed_tool_result(self, tmp_path: Path) -> None:
        """AC3: a non-existent root fails without raising."""
        result = BatchEditCheckTool().execute(
            path=str(tmp_path / "absent"),
            operations=[{"op": "delete", "file": "pkg/mod.py"}],
        )

        assert result.success is False
        assert result.error

    def test_malformed_operations_return_failed_tool_result(
        self, project: Path
    ) -> None:
        """AC3: an unknown op discriminator fails without raising."""
        result = BatchEditCheckTool().execute(
            path=str(project),
            operations=[{"op": "nope"}],
        )

        assert result.success is False
        assert result.error


class TestReadOnlyInvariant:
    """AC4: the checker never mutates the target tree."""

    def test_mixed_batch_leaves_the_tree_byte_identical(self, project: Path) -> None:
        """AC4: snapshot before == snapshot after on create/replace/delete."""
        before = _snapshot(project)

        result = BatchEditCheckTool().execute(
            path=str(project),
            operations=[
                {
                    "op": "create",
                    "file": "pkg/created.py",
                    "content": "created = True\n",
                },
                {
                    "op": "replace",
                    "file": "pkg/mod.py",
                    "edits": [{"old": "value = 1", "new": "value = 2"}],
                },
                {"op": "delete", "file": "pkg/legacy.py"},
            ],
        )

        assert result.success is True
        assert _snapshot(project) == before
