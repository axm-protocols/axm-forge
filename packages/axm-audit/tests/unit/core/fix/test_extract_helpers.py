"""Unit tests for axm_audit.core.fix.extract_helpers — helper-promotion logic."""

from __future__ import annotations

import ast
from pathlib import Path

from axm_audit.core.fix.extract_helpers import (
    _classify_assign,
    _classify_top_level_node,
    _drop_cascaded_dup,
    _DupPartition,
    _extract_shared_helpers,
    _extract_shared_helpers_once,
    _format_ambiguous_skip,
    _index_tier_scan,
    _partition_duplicates,
    _resolve_cascading_skips,
    _scan_tier,
)


def _first_node(src: str) -> ast.stmt:
    return ast.parse(src).body[0]


# ---------------------------------------------------------------------------
# _classify_assign
# ---------------------------------------------------------------------------


def test_classify_assign_accepts_uppercase_constant() -> None:
    """Top-level UPPERCASE name with a static value is classified as ``pure``."""
    node = _first_node("FOO = 42\n")
    assert isinstance(node, ast.Assign)
    result = _classify_assign(node, set())
    assert result is not None
    name, _hash, kind = result
    assert name == "FOO"
    assert kind == "pure"


def test_classify_assign_rejects_lowercase_name() -> None:
    """Lowercase names are not constant candidates."""
    node = _first_node("foo = 42\n")
    assert isinstance(node, ast.Assign)
    assert _classify_assign(node, set()) is None


def test_classify_assign_rejects_multi_target() -> None:
    """Tuple/multi-target assignments are not single-name constants."""
    node = _first_node("A = B = 1\n")
    assert isinstance(node, ast.Assign)
    assert _classify_assign(node, set()) is None


def test_classify_assign_skips_file_dunder_reference() -> None:
    """Values that reference ``__file__`` are recorded as location-skipped."""
    node = _first_node("ROOT = __file__\n")
    assert isinstance(node, ast.Assign)
    skipped: set[str] = set()
    assert _classify_assign(node, skipped) is None
    assert "ROOT" in skipped


# ---------------------------------------------------------------------------
# _classify_top_level_node
# ---------------------------------------------------------------------------


def test_classify_node_skips_test_functions() -> None:
    """Functions starting with ``test_`` are not helper candidates."""
    node = _first_node("def test_x():\n    pass\n")
    assert _classify_top_level_node(node, set()) is None


def test_classify_node_marks_pytest_fixture_as_fixture() -> None:
    """@pytest.fixture decorated function gets kind='fixture'."""
    src = "import pytest\n@pytest.fixture\ndef payload():\n    return 1\n"
    node = ast.parse(src).body[1]
    result = _classify_top_level_node(node, set())
    assert result is not None
    name, _hash, kind = result
    assert name == "payload"
    assert kind == "fixture"


def test_classify_node_plain_function_is_pure() -> None:
    """A non-fixture, non-test function is a pure helper."""
    node = _first_node("def helper():\n    return 1\n")
    result = _classify_top_level_node(node, set())
    assert result is not None
    _name, _hash, kind = result
    assert kind == "pure"


def test_classify_node_skips_test_class() -> None:
    """Test* classes are not helper candidates."""
    node = _first_node("class TestX:\n    pass\n")
    assert _classify_top_level_node(node, set()) is None


def test_classify_node_helper_class_is_pure() -> None:
    """Non-Test classes are pure helpers."""
    node = _first_node("class Helper:\n    pass\n")
    result = _classify_top_level_node(node, set())
    assert result is not None
    assert result[2] == "pure"


def test_classify_node_unknown_stmt_returns_none() -> None:
    """Non-def/non-assign top-level statements return None."""
    node = _first_node("import os\n")
    assert _classify_top_level_node(node, set()) is None


# ---------------------------------------------------------------------------
# _format_ambiguous_skip
# ---------------------------------------------------------------------------


def test_format_ambiguous_skip_groups_fixture(tmp_path: Path) -> None:
    """Ambiguous fixture across multiple bodies surfaces a helpful message."""
    f1 = tmp_path / "a.py"
    f2 = tmp_path / "b.py"
    f1.write_text("")
    f2.write_text("")
    groups = [
        ("hash1abcd", "fixture", [f1]),
        ("hash2efgh", "fixture", [f2]),
    ]
    msg = _format_ambiguous_skip("my_fx", groups, tmp_path)
    assert "ambiguous fixture `my_fx`" in msg
    assert "a.py" in msg
    assert "b.py" in msg


def test_format_ambiguous_skip_pure_helper(tmp_path: Path) -> None:
    """Pure-only ambiguous groups get the ``helper`` label."""
    f1 = tmp_path / "a.py"
    f1.write_text("")
    groups = [("h", "pure", [f1]), ("i", "pure", [f1])]
    msg = _format_ambiguous_skip("util", groups, tmp_path)
    assert "ambiguous helper `util`" in msg


# ---------------------------------------------------------------------------
# _partition_duplicates + _drop_cascaded_dup + _resolve_cascading_skips
# ---------------------------------------------------------------------------


def test_partition_duplicates_extracts_repeated_helpers(tmp_path: Path) -> None:
    """Helpers with one body in 2+ files become extraction duplicates."""
    from axm_audit.core.fix.extract_helpers import _TierIndex

    f1 = tmp_path / "a.py"
    f2 = tmp_path / "b.py"
    f1.write_text("")
    f2.write_text("")
    index = _TierIndex(
        by_name={"helper": [("hash", "pure", [f1, f2])]},
        deps_by_name={},
    )
    part = _partition_duplicates(index, tmp_path)
    assert ("helper", "hash", "pure") in part.duplicates
    assert part.skip_msgs == []


def test_partition_duplicates_marks_ambiguous_multi_body(tmp_path: Path) -> None:
    """Multiple bodies for same name -> ambiguous (skip), not duplicate."""
    from axm_audit.core.fix.extract_helpers import _TierIndex

    f1 = tmp_path / "a.py"
    f2 = tmp_path / "b.py"
    f1.write_text("")
    f2.write_text("")
    index = _TierIndex(
        by_name={
            "helper": [
                ("hash_a", "pure", [f1]),
                ("hash_b", "pure", [f2]),
            ]
        },
        deps_by_name={},
    )
    part = _partition_duplicates(index, tmp_path)
    assert part.duplicates == {}
    assert part.skip_msgs and "ambiguous helper `helper`" in part.skip_msgs[0]
    assert "helper" in part.skipped_names


def test_partition_duplicates_singleton_is_not_extracted(tmp_path: Path) -> None:
    """A helper defined in only ONE file is not an extraction target."""
    from axm_audit.core.fix.extract_helpers import _TierIndex

    f1 = tmp_path / "a.py"
    f1.write_text("")
    index = _TierIndex(
        by_name={"helper": [("hash", "pure", [f1])]},
        deps_by_name={},
    )
    part = _partition_duplicates(index, tmp_path)
    assert part.duplicates == {}
    assert part.skipped_names == set()


def test_drop_cascaded_dup_removes_and_records(tmp_path: Path) -> None:
    """_drop_cascaded_dup deletes the matching sig and emits a skip message."""
    f1 = tmp_path / "a.py"
    f1.write_text("")
    part = _DupPartition(
        duplicates={("h", "hash", "pure"): [f1]},
    )
    dropped = _drop_cascaded_dup(part, "h", {"blocker"})
    assert dropped is True
    assert part.duplicates == {}
    assert "h" in part.skipped_names
    assert any("cascading skip `h`" in m for m in part.skip_msgs)


def test_drop_cascaded_dup_returns_false_when_no_match(tmp_path: Path) -> None:
    """_drop_cascaded_dup returns False when nothing matches."""
    part = _DupPartition()
    assert _drop_cascaded_dup(part, "absent", {"x"}) is False


def test_resolve_cascading_skips_drops_dependent_duplicates(tmp_path: Path) -> None:
    """Helpers depending on a skipped name are dropped from duplicates."""
    from axm_audit.core.fix.extract_helpers import _TierIndex

    f1 = tmp_path / "a.py"
    f1.write_text("")
    index = _TierIndex(
        by_name={},
        deps_by_name={"consumer": {"blocked"}},
    )
    part = _DupPartition(
        duplicates={("consumer", "h", "pure"): [f1]},
        skipped_names={"blocked"},
    )
    _resolve_cascading_skips(part, index)
    assert part.duplicates == {}
    assert "consumer" in part.skipped_names


# ---------------------------------------------------------------------------
# _scan_tier + _index_tier_scan
# ---------------------------------------------------------------------------


def test_scan_tier_skips_init_and_conftest_and_helpers(tmp_path: Path) -> None:
    """_scan_tier ignores ``__init__.py``, ``conftest.py``, ``_helpers.py``."""
    tier = tmp_path / "integration"
    tier.mkdir()
    (tier / "__init__.py").write_text("def skip_me(): pass\n")
    (tier / "conftest.py").write_text("def skip_too(): pass\n")
    (tier / "_helpers.py").write_text("def also_skip(): pass\n")
    (tier / "test_a.py").write_text("def helper():\n    return 1\n")
    scan = _scan_tier(tier)
    paths = {p.name for p in scan.per_file}
    assert paths == {"test_a.py"}


def test_scan_tier_skips_syntax_error_files(tmp_path: Path) -> None:
    """Files that fail to parse are tolerated and skipped."""
    tier = tmp_path / "integration"
    tier.mkdir()
    (tier / "test_broken.py").write_text("def f(:\n")
    (tier / "test_ok.py").write_text("def helper():\n    return 1\n")
    scan = _scan_tier(tier)
    names = {p.name for p in scan.per_file}
    assert names == {"test_ok.py"}


def test_index_tier_scan_groups_by_name_and_signature(tmp_path: Path) -> None:
    """_index_tier_scan groups helpers by (name, body_hash, kind)."""
    tier = tmp_path / "integration"
    tier.mkdir()
    (tier / "test_a.py").write_text("def shared():\n    return 1\n")
    (tier / "test_b.py").write_text("def shared():\n    return 1\n")
    scan = _scan_tier(tier)
    index = _index_tier_scan(scan)
    assert "shared" in index.by_name
    # Same body across both files -> single group with 2 files.
    groups = index.by_name["shared"]
    assert len(groups) == 1
    assert len(groups[0][2]) == 2


# ---------------------------------------------------------------------------
# _extract_shared_helpers / _extract_shared_helpers_once
# ---------------------------------------------------------------------------


def test_extract_shared_helpers_once_returns_empty_without_tests(
    tmp_path: Path,
) -> None:
    """Without ``tests/`` directory, extraction is a no-op."""
    assert _extract_shared_helpers_once(tmp_path) == []


def test_extract_shared_helpers_once_returns_empty_without_canonical_tiers(
    tmp_path: Path,
) -> None:
    """Empty tests/ (no integration/e2e/unit) yields no extractions."""
    (tmp_path / "tests").mkdir()
    assert _extract_shared_helpers_once(tmp_path) == []


def test_extract_shared_helpers_top_level_no_tests(tmp_path: Path) -> None:
    """Top-level loop terminates immediately when no progress is made."""
    assert _extract_shared_helpers(tmp_path) == []
