"""Integration tests for the complexity-rule basename collision fix.

Two source files that share a basename and both define a function with
the same name must not collide in the cognitive-complexity map. The fix
uses ``(POSIX path relative to src_path, function_name)`` as the key,
so both writers and readers must agree on that shape — verified through
the public ``ComplexityRule.check`` surface.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from axm_audit.core.rules.complexity import ComplexityRule

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


def _foo_offenders(result_details: dict[str, object]) -> list[dict[str, object]]:
    """Return all ``foo`` entries from a ComplexityRule.check details payload."""
    offenders = result_details["top_offenders"]
    return [o for o in offenders if o["function"] == "foo"]


def test_check_assigns_distinct_cognitive_per_file(tmp_path):
    """AC1+AC2+AC4: same-basename ``foo`` keeps a per-file cognitive score.

    Drives the public ``ComplexityRule.check`` API end-to-end. If the cog
    map ever collapses both ``foo`` entries onto a single basename key, the
    two cognitive values would coincide and this test would fail.
    """
    pytest.importorskip("complexipy")
    _build_collision_tree(tmp_path)

    result = ComplexityRule().check(tmp_path)

    assert result.details is not None
    foos = _foo_offenders(result.details)
    assert len(foos) >= 2, (
        f"expected both foo offenders, got {result.details['top_offenders']}"
    )
    cogs_by_file = {o["file"]: o["cognitive"] for o in foos}
    assert len(set(cogs_by_file.values())) == 2, (
        f"expected distinct cognitive per file, got {cogs_by_file}"
    )
    assert all(cog > 0 for cog in cogs_by_file.values()), (
        f"cognitive map collapsed to zero for one file: {cogs_by_file}"
    )


def test_check_via_subprocess_assigns_distinct_cognitive_per_file(tmp_path, mocker):
    """AC3: the subprocess radon path looks cog_map up via relative POSIX key."""
    pytest.importorskip("complexipy")
    if shutil.which("radon") is None:
        pytest.skip("radon binary not available")
    _build_collision_tree(tmp_path)

    # Force the radon subprocess branch by pretending the API is missing.
    mocker.patch(
        "axm_audit.core.rules.complexity._try_import_radon",
        return_value=None,
    )

    result = ComplexityRule().check(tmp_path)

    assert result.details is not None
    foos = _foo_offenders(result.details)
    assert len(foos) >= 2, (
        f"expected both foo offenders, got {result.details['top_offenders']}"
    )
    cogs_by_file = {o["file"]: o["cognitive"] for o in foos}
    assert len(set(cogs_by_file.values())) == 2, (
        f"expected distinct cognitive per file, got {cogs_by_file}"
    )
