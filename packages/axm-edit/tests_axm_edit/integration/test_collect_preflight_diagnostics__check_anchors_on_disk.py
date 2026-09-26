"""Integration tests: preflight anchors carrying quotes, on a real root."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_edit.core.preflight import collect_preflight_diagnostics

pytestmark = pytest.mark.integration

DOC_MODULE = 'def f():\n    """Old doc."""\n    return 1\n'


def _replace(old: str) -> list[dict[str, object]]:
    """One replace operation on ``mod.py`` with a single edit."""
    return [
        {
            "op": "replace",
            "file": "mod.py",
            "edits": [{"old": old, "new": "    pass"}],
        }
    ]


def test_triple_quoted_anchor_passes_the_preflight(tmp_path: Path) -> None:
    """A docstring anchor raises no diagnostic at all."""
    (tmp_path / "mod.py").write_text(DOC_MODULE, encoding="utf-8")

    diagnostics = collect_preflight_diagnostics(
        tmp_path, _replace('    """Old doc."""')
    )

    assert diagnostics == []


def test_over_escaped_quotes_get_a_dedicated_hint(tmp_path: Path) -> None:
    """Backslash-escaped quotes absent from the file are named in the hint."""
    (tmp_path / "mod.py").write_text(DOC_MODULE, encoding="utf-8")
    over_escaped = '    \\"\\"\\"Old doc.\\"\\"\\"'

    diagnostics = collect_preflight_diagnostics(tmp_path, _replace(over_escaped))

    assert [d.code for d in diagnostics] == ["ANCHOR_NOT_FOUND"]
    assert "backslash-escaped quotes" in diagnostics[0].hint


def test_plain_miss_keeps_the_generic_hint(tmp_path: Path) -> None:
    """A miss unrelated to escaping keeps the re-read hint."""
    (tmp_path / "mod.py").write_text(DOC_MODULE, encoding="utf-8")

    diagnostics = collect_preflight_diagnostics(tmp_path, _replace("    return 2"))

    assert [d.code for d in diagnostics] == ["ANCHOR_NOT_FOUND"]
    assert "backslash" not in diagnostics[0].hint
