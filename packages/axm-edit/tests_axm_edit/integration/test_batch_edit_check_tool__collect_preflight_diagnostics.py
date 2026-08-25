"""Integration tests for BatchEditCheckTool over the shared preflight core.

Real filesystem (``tmp_path``), strictly read-only: pins the per-operation
diagnostic ordering and the severity partition the tool must surface once its
private pipeline delegates to ``axm_edit.core.preflight``.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import cast

import pytest

from axm_edit.core.preflight import collect_preflight_diagnostics
from axm_edit.tools.batch_edit_check import BatchEditCheckTool

pytestmark = pytest.mark.integration

_LONG_NEW_LINE = "other = " + "9" * 100


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A real tree declaring a 120-char ruff limit plus two modules."""
    (tmp_path / "pyproject.toml").write_text(
        "[tool.ruff]\nline-length = 120\n",
        encoding="utf-8",
    )
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "mod.py").write_text("value = 1\nother = 2\n", encoding="utf-8")
    (package / "legacy.py").write_text("legacy = True\n", encoding="utf-8")
    return tmp_path


def _diagnostics(data: dict[str, object] | None) -> list[dict[str, object]]:
    """Return the serialised diagnostics of a ``batch_edit_check`` payload."""
    assert data is not None
    return cast("list[dict[str, object]]", data["diagnostics"])


def test_diagnostics_follow_operation_order_with_the_anchor_first(
    project: Path,
) -> None:
    """AC1: the payload is ordered per operation, anchor before unknown key.

    Operation 0 carries a missing ``old`` anchor and an unknown edit key,
    operation 1 only the unknown key ``replace_all``: the emitted sequence
    must be the core's per-operation one, not the family-grouped one that
    puts every unknown-key finding first.
    """
    result = BatchEditCheckTool().execute(
        path=str(project),
        operations=[
            {
                "op": "replace",
                "file": "pkg/mod.py",
                "edits": [
                    {
                        "old": "value = 404",
                        "new": "value = 2",
                        "replace_all": True,
                    }
                ],
            },
            {
                "op": "replace",
                "file": "pkg/legacy.py",
                "edits": [
                    {
                        "old": "legacy = True",
                        "new": "legacy = False",
                        "replace_all": True,
                    }
                ],
            },
        ],
    )

    assert result.success is True
    diagnostics = _diagnostics(result.data)

    assert [item["op_index"] for item in diagnostics] == [0, 0, 1]
    assert [item["code"] for item in diagnostics] == [
        "ANCHOR_NOT_FOUND",
        "UNKNOWN_EDIT_KEY",
        "UNKNOWN_EDIT_KEY",
    ]
    assert "value = 404" in str(diagnostics[0]["message"])
    assert "replace_all" in str(diagnostics[1]["message"])


def test_payload_exposes_blocking_and_severity_counts(project: Path) -> None:
    """AC2: blocking / error_count / warning_count sit next to the old keys.

    Operation 0 misses its anchor (error) and operation 1 writes a line wider
    than the 88-char default but within the configured 120 (warning).
    """
    result = BatchEditCheckTool().execute(
        path=str(project),
        operations=[
            {
                "op": "replace",
                "file": "pkg/mod.py",
                "edits": [{"old": "value = 404", "new": "value = 2"}],
            },
            {
                "op": "replace",
                "file": "pkg/mod.py",
                "edits": [{"old": "other = 2", "new": _LONG_NEW_LINE}],
            },
        ],
    )

    assert result.success is True
    data = result.data
    assert data is not None

    assert data.get("blocking") is True
    assert data.get("error_count") == 1
    assert data.get("warning_count") == 1
    assert data["ok"] is False
    assert [item["code"] for item in _diagnostics(data)] == [
        "ANCHOR_NOT_FOUND",
        "LINE_LENGTH_DEFAULT_MISMATCH",
    ]


def test_check_tool_and_preflight_agree_on_a_rewrite_batch(
    project: Path,
) -> None:
    """AC4: both paths emit the identical ordered (code, file) sequence.

    One stale rewrite (digest taken before the file was mutated) and one
    valid rewrite in the same batch: the tool payload must repeat, in the
    same order, exactly what ``collect_preflight_diagnostics`` returns.
    """
    stale_target = project / "pkg" / "mod.py"
    stale_digest = hashlib.sha256(stale_target.read_bytes()).hexdigest()
    stale_target.write_text("value = 99\n", encoding="utf-8")
    fresh_target = project / "pkg" / "legacy.py"
    fresh_digest = hashlib.sha256(fresh_target.read_bytes()).hexdigest()
    raw_ops: list[dict[str, object]] = [
        {
            "op": "rewrite",
            "file": "pkg/mod.py",
            "content": "value = 3\n",
            "checksum": stale_digest,
        },
        {
            "op": "rewrite",
            "file": "pkg/legacy.py",
            "content": "legacy = False\n",
            "checksum": fresh_digest,
        },
    ]

    result = BatchEditCheckTool().execute(path=str(project), operations=raw_ops)
    expected = [
        (item.code.upper(), item.file)
        for item in collect_preflight_diagnostics(project, raw_ops)
    ]

    assert result.success is True
    observed = [
        (str(item["code"]).upper(), item["file"]) for item in _diagnostics(result.data)
    ]
    assert observed == expected
    assert expected == [("REWRITE_CHECKSUM_STALE", "pkg/mod.py")]
