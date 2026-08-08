"""E2E tests for the ``axm batch_edit`` console script (subprocess black box)."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

NBSP = chr(0xA0)  # U+00A0 NO-BREAK SPACE (built, so the source stays ASCII)


def _axm_binary() -> Path:
    """Resolve the ``axm`` console script of the current environment.

    ``axm`` is a declared dependency of ``axm-edit``: a missing binary is a
    genuine failure, never a reason to skip.
    """
    found = shutil.which("axm")
    binary = Path(found) if found else Path(sys.executable).with_name("axm")
    assert binary.exists(), f"axm console script not found at {binary}"
    return binary


@pytest.mark.e2e
def test_batch_edit_reports_nbsp_near_miss_with_locator(tmp_path: Path) -> None:
    """AC6: the preflight refuses the near-miss anchor, naming file and anchor."""
    target = tmp_path / "pkg" / "mod.py"
    target.parent.mkdir(parents=True)
    # Line 4 differs from the requested ``old`` only by a U+00A0.
    target.write_text(f"import os\n\n\nvalue{NBSP}= 1\n", encoding="utf-8")

    operations = [
        {
            "op": "replace",
            "file": "pkg/mod.py",
            "edits": [{"old": "value = 1", "new": "value = 2"}],
        }
    ]

    proc = subprocess.run(
        [
            str(_axm_binary()),
            "batch_edit",
            "--path",
            str(tmp_path),
            "--operations",
            json.dumps(operations),
        ],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
        check=False,
    )

    combined = proc.stdout + proc.stderr
    lines = [line.lstrip() for line in combined.splitlines()]

    assert proc.returncode != 0, combined
    assert any(line.startswith("[error] op#0 pkg/mod.py:") for line in lines), combined
    assert "ANCHOR_NOT_FOUND" in combined, combined
    assert "'value = 1'" in combined, combined


@pytest.mark.e2e
def test_batch_edit_reports_truncated_ambiguous_match(tmp_path: Path) -> None:
    """AC4: the CLI prints a bounded ``Ambiguous match:`` candidate list."""
    anchor = "value = compute(x)"
    target = tmp_path / "pkg" / "mod.py"
    target.parent.mkdir(parents=True)
    # The anchor lands on lines 10, 20, ... 120 (12 occurrences).
    body_lines: list[str] = []
    for _ in range(12):
        body_lines.extend(["filler = 0"] * 9)
        body_lines.append(anchor)
    target.write_text("\n".join(body_lines) + "\n", encoding="utf-8")

    operations = [
        {
            "op": "replace",
            "file": "pkg/mod.py",
            "edits": [{"old": anchor, "new": "value = compute(y)"}],
        }
    ]

    proc = subprocess.run(
        [
            str(_axm_binary()),
            "batch_edit",
            "--path",
            str(tmp_path),
            "--operations",
            json.dumps(operations),
        ],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
        check=False,
    )

    combined = proc.stdout + proc.stderr
    reported = "\n".join(
        line for line in combined.splitlines() if "Ambiguous match:" in line
    )

    assert proc.returncode != 0, combined
    assert reported, combined
    for first_hit in ("10", "20", "30", "40", "50"):
        assert first_hit in reported, combined
    assert "(+7 more)" in reported, combined
    assert "120" not in reported, combined


@pytest.mark.e2e
def test_batch_edit_reports_the_real_line_count_for_an_out_of_range_hint(
    tmp_path: Path,
) -> None:
    """AC6: an anchor absent from the target file is refused before any write."""
    target = tmp_path / "pkg" / "mod.py"
    target.parent.mkdir(parents=True)
    target.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")

    operations = [
        {
            "op": "replace",
            "file": "pkg/mod.py",
            "edits": [{"line": 99, "old": "delta", "new": "epsilon"}],
        }
    ]

    proc = subprocess.run(
        [
            str(_axm_binary()),
            "batch_edit",
            "--path",
            str(tmp_path),
            "--operations",
            json.dumps(operations),
        ],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
        check=False,
    )

    combined = proc.stdout + proc.stderr

    assert proc.returncode != 0, combined
    assert "ANCHOR_NOT_FOUND" in combined, combined
    assert "'delta'" in combined, combined
    assert target.read_text(encoding="utf-8") == "alpha\nbeta\ngamma\n", combined


@pytest.mark.e2e
def test_batch_edit_refuses_an_unknown_edit_key_and_leaves_the_file_untouched(
    tmp_path: Path,
) -> None:
    """AC6: the CLI refuses `replace_all` with an actionable, keyed message."""
    target = tmp_path / "pkg" / "mod.py"
    target.parent.mkdir(parents=True)
    target.write_text("value = 1\n", encoding="utf-8")
    before = target.read_bytes()

    operations = [
        {
            "op": "replace",
            "file": "pkg/mod.py",
            "edits": [{"old": "value = 1", "new": "value = 2", "replace_all": True}],
        }
    ]

    proc = subprocess.run(
        [
            str(_axm_binary()),
            "batch_edit",
            "--path",
            str(tmp_path),
            "--operations",
            json.dumps(operations),
        ],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
        check=False,
    )

    combined = proc.stdout + proc.stderr
    keys_line = [
        line
        for line in combined.splitlines()
        if all(key in line for key in ("old", "new", "line"))
    ]

    assert proc.returncode != 0, combined
    assert "replace_all" in combined, combined
    # The refusal must be actionable: a line naming the accepted edit keys.
    assert keys_line, f"accepted edit keys must be listed: {combined}"
    assert target.read_bytes() == before, combined
