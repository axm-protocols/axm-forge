from __future__ import annotations

from typing import Any

import libcst as cst

from axm_anvil.core.shared import SharedInfo, _classify_shared_helpers


def _make_block(name: str, refs: set[str]) -> Any:
    return type(
        "Block",
        (),
        {
            "name": name,
            "node": None,
            "leading_lines": [],
            "referenced_names": refs,
        },
    )()


def test_classify_shared_helper_direct():
    blocks = [_make_block("moved_A", {"_h"})]
    needed_helpers = {"_h"}
    source_after = cst.parse_module(
        "def remaining_B():\n    return _h()\n\ndef _h():\n    return 1\n"
    )
    result = _classify_shared_helpers(blocks, needed_helpers, source_after)
    assert "_h" in result
    info = result["_h"]
    assert isinstance(info, SharedInfo)
    assert info.used_by_moved == {"moved_A"}
    assert info.used_by_remaining == {"remaining_B"}


def test_classify_shared_helper_moved_only():
    blocks = [_make_block("moved_A", {"_h"})]
    needed_helpers = {"_h"}
    source_after = cst.parse_module("def remaining_B():\n    return 1\n")
    result = _classify_shared_helpers(blocks, needed_helpers, source_after)
    assert result == {}


def test_classify_shared_helper_remaining_only():
    blocks = [_make_block("moved_A", set())]
    needed_helpers: set[str] = set()
    source_after = cst.parse_module(
        "def remaining_B():\n    return _h()\n\ndef _h():\n    return 1\n"
    )
    result = _classify_shared_helpers(blocks, needed_helpers, source_after)
    assert result == {}


def test_classify_shared_transitive_chain():
    blocks = [_make_block("moved_A", {"_a"})]
    needed_helpers = {"_a"}
    source_after = cst.parse_module(
        "def remaining_B():\n    return _b()\n\n"
        "def _b():\n    return _a()\n\n"
        "def _a():\n    return 1\n"
    )
    result = _classify_shared_helpers(blocks, needed_helpers, source_after)
    assert "_a" in result
    info = result["_a"]
    assert "moved_A" in info.used_by_moved
    assert "remaining_B" in info.used_by_remaining
