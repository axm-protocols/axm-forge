"""Integration tests for the complexity-rule basename collision fix.

Two source files that share a basename and both define a function with
the same name must not collide in the cognitive-complexity map. The fix
uses ``(POSIX path relative to src_path, function_name)`` as the key,
so both writers and readers must agree on that shape.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from axm_audit.core.rules.complexity import (
    ComplexityRule,
    _compute_cognitive_map,
    _parse_complexipy_entries,
    _try_import_complexipy,
)

pytestmark = pytest.mark.integration


# Flat fan-out: high cyclomatic (>=11), low cognitive (depth 1 each).
FOO_FLAT = """\
def foo(x):
    if x == 0: return 0
    if x == 1: return 1
    if x == 2: return 2
    if x == 3: return 3
    if x == 4: return 4
    if x == 5: return 5
    if x == 6: return 6
    if x == 7: return 7
    if x == 8: return 8
    if x == 9: return 9
    if x == 10: return 10
    if x == 11: return 11
    return -1
"""

# Deeply nested: moderate cyclomatic, very high cognitive (>15).
FOO_NESTED = """\
def foo(x):
    if x > 0:
        if x > 1:
            if x > 2:
                if x > 3:
                    if x > 4:
                        if x > 5:
                            if x > 6:
                                return 1
    return 0
"""


def _build_collision_tree(root: Path) -> Path:
    """Create ``src/a/utils.py`` and ``src/b/utils.py`` both defining ``foo``."""
    src = root / "src"
    (src / "a").mkdir(parents=True)
    (src / "b").mkdir(parents=True)
    (src / "__init__.py").write_text("", encoding="utf-8")
    (src / "a" / "__init__.py").write_text("", encoding="utf-8")
    (src / "b" / "__init__.py").write_text("", encoding="utf-8")
    (src / "a" / "utils.py").write_text(FOO_FLAT, encoding="utf-8")
    (src / "b" / "utils.py").write_text(FOO_NESTED, encoding="utf-8")
    return src


def _require_complexipy_api() -> None:
    if _try_import_complexipy() is None:
        pytest.skip("complexipy Python API not importable")


def test_cognitive_map_distinguishes_same_basename(tmp_path):
    """AC1, AC4: cog_map keys disambiguate same-basename source files."""
    _require_complexipy_api()
    src = _build_collision_tree(tmp_path)

    cog_map, disabled = _compute_cognitive_map(src)

    assert not disabled
    key_a = ("a/utils.py", "foo")
    key_b = ("b/utils.py", "foo")
    assert key_a in cog_map, f"expected {key_a} in {sorted(cog_map)}"
    assert key_b in cog_map, f"expected {key_b} in {sorted(cog_map)}"
    assert cog_map[key_a] != cog_map[key_b], (
        f"expected distinct cognitive scores per file, got {cog_map[key_a]} for both"
    )


def test_check_via_api_assigns_correct_cognitive_per_file(tmp_path):
    """AC2, AC4: ComplexityRule.check returns the right cog per file."""
    _require_complexipy_api()
    src = _build_collision_tree(tmp_path)
    cog_map, _ = _compute_cognitive_map(src)
    expected = {
        cog_map[("a/utils.py", "foo")],
        cog_map[("b/utils.py", "foo")],
    }
    assert len(expected) == 2, f"fixture should yield distinct cogs, got {expected}"

    result = ComplexityRule().check(tmp_path)

    assert result.details is not None
    offenders = result.details["top_offenders"]
    foos = [o for o in offenders if o["function"] == "foo"]
    assert len(foos) >= 2, f"expected both foo offenders, got {offenders}"
    cogs_by_file = {o["file"]: o["cognitive"] for o in foos}
    assert set(cogs_by_file.values()) == expected, (
        f"expected per-file cogs {expected}, got {cogs_by_file}"
    )


def test_process_radon_output_uses_relative_path_lookup(tmp_path, mocker):
    """AC3: the subprocess radon path looks cog_map up via relative POSIX key."""
    _require_complexipy_api()
    if shutil.which("radon") is None:
        pytest.skip("radon binary not available")
    src = _build_collision_tree(tmp_path)
    cog_map, _ = _compute_cognitive_map(src)
    expected = {
        cog_map[("a/utils.py", "foo")],
        cog_map[("b/utils.py", "foo")],
    }
    assert len(expected) == 2

    # Force the radon subprocess branch by pretending the API is missing.
    mocker.patch(
        "axm_audit.core.rules.complexity._try_import_radon",
        return_value=None,
    )

    result = ComplexityRule().check(tmp_path)

    assert result.details is not None
    offenders = result.details["top_offenders"]
    foos = [o for o in offenders if o["function"] == "foo"]
    assert len(foos) >= 2, f"expected both foo offenders, got {offenders}"
    cogs_by_file = {o["file"]: o["cognitive"] for o in foos}
    assert set(cogs_by_file.values()) == expected, (
        f"expected per-file cogs {expected}, got {cogs_by_file}"
    )


def test_complexipy_entry_outside_src_path_falls_back_to_basename(tmp_path):
    """AC1: entries with paths outside src_path fall back to basename."""
    src = tmp_path / "src"
    src.mkdir()
    entries = json.loads(
        json.dumps(
            [
                {
                    "file_name": "/some/unrelated/path/utils.py",
                    "function_name": "foo",
                    "complexity": 7,
                }
            ]
        )
    )

    result = _parse_complexipy_entries(entries, src)

    assert ("utils.py", "foo") in result, f"got keys {sorted(result)}"
    assert result[("utils.py", "foo")] == 7
