"""Integration tests for collect_preflight_diagnostics over a real root."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from axm_edit.core.preflight import (
    collect_preflight_diagnostics,
    partition_diagnostics,
)

pytestmark = pytest.mark.integration


def _write(root: Path, name: str, text: str) -> None:
    """Write a real file under *root*, creating parents as needed."""
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _snapshot(root: Path) -> dict[str, str]:
    """Map every file under *root* to the sha256 of its bytes."""
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_collect_preflight_diagnostics_merges_static_and_fs_diagnostics(
    tmp_path: Path,
) -> None:
    """AC1: two calls on the same batch return an equal, op-ordered list."""
    _write(tmp_path, "kept.py", "value = 1\nvalue = 1\n")
    _write(tmp_path, "existing.py", "already = True\n")
    raw_ops: list[dict[str, object]] = [
        {
            "op": "replace",
            "file": "kept.py",
            "edits": [{"old": "value = 1", "new": "value = 2"}],
        },
        {"op": "create", "file": "existing.py", "content": "x = 1\n"},
    ]

    first = collect_preflight_diagnostics(tmp_path, raw_ops)
    second = collect_preflight_diagnostics(tmp_path, raw_ops)

    assert first == second
    assert [item.op_index for item in first] == sorted(item.op_index for item in first)
    assert {item.code for item in first} >= {
        "ANCHOR_AMBIGUOUS",
        "CREATE_ON_EXISTING",
    }


def test_unknown_edit_key_is_reported_with_its_operation_index(
    tmp_path: Path,
) -> None:
    """AC3: `replace_all` is named and carries the offending op index."""
    _write(tmp_path, "a.py", "value = 1\n")
    _write(tmp_path, "b.py", "other = 2\n")
    raw_ops: list[dict[str, object]] = [
        {
            "op": "replace",
            "file": "a.py",
            "edits": [{"old": "value = 1", "new": "value = 3"}],
        },
        {
            "op": "replace",
            "file": "b.py",
            "edits": [{"old": "other = 2", "new": "other = 4", "replace_all": True}],
        },
    ]

    diagnostics = collect_preflight_diagnostics(tmp_path, raw_ops)

    unknown = [item for item in diagnostics if "replace_all" in item.message]
    assert len(unknown) == 1
    assert unknown[0].op_index == 1
    assert unknown[0].code == "UNKNOWN_EDIT_KEY"


def test_blocking_rules_and_line_length_warning_share_one_batch(
    tmp_path: Path,
) -> None:
    """AC4: create/anchor rules block while an over-long line only warns."""
    (tmp_path / "pyproject.toml").write_text(
        "[tool.ruff]\nline-length = 120\n", encoding="utf-8"
    )
    _write(tmp_path, "existing.py", "already = True\n")
    _write(tmp_path, "dup.py", "flag = 1\nflag = 1\n")
    _write(tmp_path, "target.py", "anchor = 0\n")
    long_line = "x = " + repr("a" * 100)
    raw_ops: list[dict[str, object]] = [
        {"op": "create", "file": "existing.py", "content": "x = 1\n"},
        {
            "op": "replace",
            "file": "dup.py",
            "edits": [{"old": "flag = 1", "new": "flag = 2"}],
        },
        {
            "op": "replace",
            "file": "target.py",
            "edits": [{"old": "missing = 42", "new": "missing = 43"}],
        },
        {
            "op": "replace",
            "file": "target.py",
            "edits": [{"old": "anchor = 0", "new": long_line}],
        },
    ]

    report = partition_diagnostics(collect_preflight_diagnostics(tmp_path, raw_ops))

    assert report.blocking is True
    assert {"CREATE_ON_EXISTING", "ANCHOR_NOT_FOUND"} <= {
        item.code for item in report.errors
    }
    long_warnings = [
        item for item in report.warnings if item.code == "LINE_LENGTH_DEFAULT_MISMATCH"
    ]
    assert len(long_warnings) == 1
    assert all(item.code != "LINE_LENGTH_DEFAULT_MISMATCH" for item in report.errors)


def test_collect_preflight_diagnostics_performs_no_write(tmp_path: Path) -> None:
    """AC5: the root tree is byte-for-byte identical after the call."""
    _write(tmp_path, "existing.py", "already = True\n")
    _write(tmp_path, "target.py", "anchor = 0\n")
    _write(tmp_path, "doomed.py", "gone = True\n")
    before = _snapshot(tmp_path)
    raw_ops: list[dict[str, object]] = [
        {"op": "create", "file": "fresh.py", "content": "fresh = 1\n"},
        {
            "op": "replace",
            "file": "target.py",
            "edits": [{"old": "anchor = 0", "new": "anchor = 1"}],
        },
        {"op": "delete", "file": "doomed.py"},
    ]

    collect_preflight_diagnostics(tmp_path, raw_ops)

    assert _snapshot(tmp_path) == before
    assert not (tmp_path / "fresh.py").exists()
    assert (tmp_path / "doomed.py").read_text(encoding="utf-8") == "gone = True\n"


def test_rewrite_unknown_key_is_reported_on_a_real_root(tmp_path: Path) -> None:
    """AC3: an out-of-schema rewrite key surfaces through the preflight."""
    _write(tmp_path, "mod.py", "value = 1\n")
    digest = hashlib.sha256((tmp_path / "mod.py").read_bytes()).hexdigest()
    raw_ops: list[dict[str, object]] = [
        {
            "op": "rewrite",
            "file": "mod.py",
            "content": "value = 2\n",
            "checksum": digest,
            "overwrite": True,
        }
    ]

    diagnostics = collect_preflight_diagnostics(tmp_path, raw_ops)

    unknown = [
        item for item in diagnostics if item.code.upper() == "REWRITE_UNKNOWN_KEY"
    ]
    assert len(unknown) == 1
    assert unknown[0].op_index == 0
    assert unknown[0].file == "mod.py"
    assert "overwrite" in unknown[0].message


def test_clean_anchor_stays_silent_next_to_a_faulty_long_one(tmp_path: Path) -> None:
    """AC5: only the long quoted anchor is reported, with a bounded excerpt."""
    body = "a" * 150
    quoted = f'"""\n{body}\n{body}\n"""'
    _write(tmp_path, "mod.py", f"    value = 1\n{quoted}\n")
    before = _snapshot(tmp_path)
    mtime = (tmp_path / "mod.py").stat().st_mtime
    raw_ops: list[dict[str, object]] = [
        {
            "op": "replace",
            "file": "mod.py",
            "edits": [
                {"old": "    value = 1", "new": "    value = 2"},
                {"old": quoted, "new": "pass"},
            ],
        }
    ]

    diagnostics = collect_preflight_diagnostics(tmp_path, raw_ops)

    assert len(diagnostics) == 1
    diagnostic = diagnostics[0]
    assert diagnostic.code == "ANCHOR_TRIPLE_QUOTE"
    assert diagnostic.op_index == 0
    assert diagnostic.edit_index == 1
    excerpt = diagnostic.anchor_excerpt
    assert excerpt is not None
    assert len(excerpt) <= 80
    assert excerpt.endswith(("…", "..."))
    assert "\n" not in excerpt
    assert _snapshot(tmp_path) == before
    assert (tmp_path / "mod.py").stat().st_mtime == mtime
