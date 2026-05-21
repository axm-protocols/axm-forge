"""Integration tests for layout_and_move + stages_execute.

Real filesystem + git + libcst + anvil. Each test gets an isolated
tmp_path package via the ``make_test_pkg`` fixture.
"""

from __future__ import annotations

import ast
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from axm_audit.core.fix.layout_and_move import (
    _resolve_conftest_shadowing,
    _resolve_helper_conflicts,
    _safe_move_units,
    flatten_tier_layout,
    relocate_non_canonical_tiers,
)
from axm_audit.core.fix.models import FileOp
from axm_audit.core.fix.stages_execute import execute

pytestmark = pytest.mark.integration


def _anvil_available() -> bool:
    try:
        from axm_audit.core.fix.layout_and_move import move_symbols
    except ImportError:
        return False
    return move_symbols is not None


@pytest.fixture
def make_test_pkg(tmp_path: Path) -> Callable[[dict[str, str]], Path]:
    """Build a minimal git-initialised package with the given source files."""

    def _make(sources: dict[str, str]) -> Path:
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "pyproject.toml").write_text(
            '[project]\nname = "pkg"\nversion = "0.0.0"\nrequires-python = ">=3.12"\n'
        )
        (pkg / "src").mkdir()
        (pkg / "src" / "pkg").mkdir()
        (pkg / "src" / "pkg" / "__init__.py").write_text("")
        (pkg / "tests").mkdir()
        for rel, content in sources.items():
            f = pkg / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(content)
        subprocess.run(["git", "init", "-q"], cwd=pkg, check=True, capture_output=True)  # noqa: S607
        subprocess.run(["git", "config", "user.email", "t@t"], cwd=pkg, check=True)  # noqa: S607
        subprocess.run(["git", "config", "user.name", "t"], cwd=pkg, check=True)  # noqa: S607
        subprocess.run(["git", "add", "-A"], cwd=pkg, check=True, capture_output=True)  # noqa: S607
        subprocess.run(
            ["git", "commit", "-q", "-m", "init"],  # noqa: S607
            cwd=pkg,
            check=True,
            capture_output=True,
        )
        return pkg

    return _make


def test_relocate_non_canonical_tiers_moves_functional_to_integration(
    make_test_pkg,
):
    """AC1: tests/functional/test_x.py -> tests/integration/test_x.py."""
    pkg = make_test_pkg(
        {
            "tests/functional/test_x.py": "def test_one():\n    assert True\n",
        }
    )

    relocate_non_canonical_tiers(pkg)

    assert (pkg / "tests" / "integration" / "test_x.py").exists()
    assert not (pkg / "tests" / "functional").exists()


def test_flatten_tier_layout_collapses_subdirectory(make_test_pkg):
    """AC2: tests/integration/foo/test_x.py -> tests/integration/test_x.py."""
    pkg = make_test_pkg(
        {
            "tests/integration/foo/test_x.py": ("def test_one():\n    assert True\n"),
        }
    )

    flatten_tier_layout(pkg)

    assert (pkg / "tests" / "integration" / "test_x.py").exists()


def test_flatten_tier_layout_refuses_on_collision(make_test_pkg):
    """AC2: flatten preserves both files on tier-root name collision."""
    pkg = make_test_pkg(
        {
            "tests/integration/test_x.py": ("def test_one():\n    assert True\n"),
            "tests/integration/foo/test_x.py": ("def test_two():\n    assert True\n"),
        }
    )

    msgs = flatten_tier_layout(pkg)

    # Original at tier root is preserved as-is.
    original = (pkg / "tests" / "integration" / "test_x.py").read_text()
    assert "test_one" in original
    # The nested file's contents survive — either renamed at tier root
    # (e.g. test_foo_x.py) or left in place when flatten refuses.
    renamed_candidates = list((pkg / "tests" / "integration").glob("test_*.py"))
    nested_kept = (pkg / "tests" / "integration" / "foo" / "test_x.py").exists()
    survived = nested_kept or any(
        "test_two" in p.read_text() for p in renamed_candidates
    )
    assert survived
    # Some signal — either a rename msg or a warning — must be surfaced.
    assert msgs


def test_safe_move_units_extracts_function_with_import_rewrite(make_test_pkg):
    """AC3: _safe_move_units relocates a unit from source to target."""
    if not _anvil_available():
        pytest.skip("axm-anvil not installed")
    pkg = make_test_pkg(
        {
            "tests/__init__.py": "",
            "tests/integration/__init__.py": "",
            "tests/integration/test_a.py": ("def test_alpha():\n    assert True\n"),
            "tests/integration/test_b.py": ("def test_beta():\n    assert True\n"),
        }
    )
    source = pkg / "tests" / "integration" / "test_a.py"
    target = pkg / "tests" / "integration" / "test_b.py"

    _safe_move_units(source, target, ["test_alpha"], pkg)

    assert "test_alpha" in target.read_text()


def test_resolve_helper_conflicts_warns_on_divergent_bodies(make_test_pkg):
    """AC4: _resolve_helper_conflicts renames helpers with divergent bodies."""
    source_code = (
        "def _helper(x):\n"
        "    return x + 1\n\n"
        "def test_one():\n"
        "    assert _helper(1) == 2\n"
    )
    target_code = (
        "def _helper(x):\n"
        "    return x + 2\n\n"
        "def test_two():\n"
        "    assert _helper(1) == 3\n"
    )
    pkg = make_test_pkg(
        {
            "tests/integration/test_a.py": source_code,
            "tests/integration/test_b.py": target_code,
        }
    )
    source_tree = ast.parse(source_code)
    target_tree = ast.parse(target_code)

    rename = _resolve_helper_conflicts(
        source_tree,
        target_tree,
        ["test_one"],
        source_stem="a",
        target=pkg / "tests/integration/test_b.py",
        project_path=pkg,
    )

    assert "_helper" in rename
    # _resolve_helper_conflicts is pure — disk content untouched.
    assert (pkg / "tests/integration/test_a.py").read_text() == source_code
    assert (pkg / "tests/integration/test_b.py").read_text() == target_code


def test_resolve_conftest_shadowing_warns(make_test_pkg):
    """AC5: _resolve_conftest_shadowing detects target-local conftest shadow."""
    conftest = "import pytest\n\n@pytest.fixture\ndef shared_fix():\n    return 1\n"
    source_code = "def test_one(shared_fix):\n    assert shared_fix == 1\n"
    target_code = (
        "import pytest\n\n"
        "@pytest.fixture\n"
        "def shared_fix():\n"
        "    return 99\n\n"
        "def test_two(shared_fix):\n"
        "    assert shared_fix == 99\n"
    )
    pkg = make_test_pkg(
        {
            "tests/conftest.py": conftest,
            "tests/integration/test_a.py": source_code,
            "tests/integration/test_b.py": target_code,
        }
    )
    source_tree = ast.parse(source_code)
    target_tree = ast.parse(target_code)

    rename = _resolve_conftest_shadowing(
        source_tree,
        target_tree,
        ["test_one"],
        target=pkg / "tests/integration/test_b.py",
        project_path=pkg,
        target_stem="b",
    )

    assert "shared_fix" in rename


def test_execute_relocate_cross_tier_with_depth_patch(make_test_pkg):
    """AC6: relocate across tiers patches Path(__file__).parents[N] depth."""
    body = (
        "from pathlib import Path\n\n"
        "def test_one():\n"
        "    root = Path(__file__).parents[2]\n"
        "    assert root.exists()\n"
    )
    pkg = make_test_pkg(
        {
            "tests/integration/foo/test_x.py": body,
        }
    )
    source = pkg / "tests/integration/foo/test_x.py"
    target = pkg / "tests/unit/test_x.py"
    op = FileOp(
        kind="relocate",
        source=source,
        target=target,
        rationale="re-tier",
        source_rule="PYRAMID_LEVEL",
    )

    execute([op], pkg)

    assert target.exists()
    assert "parents[1]" in target.read_text()


def test_execute_rename_updates_cross_imports(make_test_pkg):
    """AC7: rename git-mvs the file and rewrites cross-test imports."""
    pkg = make_test_pkg(
        {
            "tests/__init__.py": "",
            "tests/integration/__init__.py": "",
            "tests/integration/test_old.py": ("def helper():\n    return 1\n"),
            "tests/integration/test_other.py": (
                "from tests.integration.test_old import helper\n\n"
                "def test_one():\n"
                "    assert helper() == 1\n"
            ),
        }
    )
    source = pkg / "tests/integration/test_old.py"
    target = pkg / "tests/integration/test_new.py"
    op = FileOp(
        kind="rename",
        source=source,
        target=target,
        rationale="canonical-name",
        source_rule="TEST_QUALITY_FILE_NAMING",
    )

    execute([op], pkg)

    assert target.exists()
    other = (pkg / "tests/integration/test_other.py").read_text()
    assert "test_new" in other


def test_execute_split_produces_target_files(make_test_pkg):
    """AC8: split produces N target files from one source."""
    if not _anvil_available():
        pytest.skip("axm-anvil not installed")
    pkg = make_test_pkg(
        {
            "tests/__init__.py": "",
            "tests/integration/__init__.py": "",
            "tests/integration/test_x.py": (
                "def test_one():\n    assert True\n\ndef test_two():\n    assert True\n"
            ),
        }
    )
    source = pkg / "tests/integration/test_x.py"
    target_a = pkg / "tests/integration/test_a.py"
    target_b = pkg / "tests/integration/test_b.py"
    op = FileOp(
        kind="split",
        source=source,
        target=[target_a, target_b],
        rationale="file-too-large",
        source_rule="TEST_QUALITY_FILE_SIZE",
        split_map={
            "test_a.py": ["test_one"],
            "test_b.py": ["test_two"],
        },
    )

    execute([op], pkg)

    assert target_a.exists()
    assert target_b.exists()


def test_execute_merge_concatenates_units_into_anchor(make_test_pkg):
    """AC9: merge moves all units into target and removes source."""
    if not _anvil_available():
        pytest.skip("axm-anvil not installed")
    pkg = make_test_pkg(
        {
            "tests/__init__.py": "",
            "tests/integration/__init__.py": "",
            "tests/integration/test_a.py": ("def test_alpha():\n    assert True\n"),
            "tests/integration/test_b.py": ("def test_beta():\n    assert True\n"),
        }
    )
    source = pkg / "tests/integration/test_b.py"
    target = pkg / "tests/integration/test_a.py"
    op = FileOp(
        kind="merge",
        source=source,
        target=target,
        rationale="too-small",
        source_rule="TEST_QUALITY_FILE_SIZE",
    )

    execute([op], pkg)

    assert not source.exists()
    body = target.read_text()
    assert "test_beta" in body
    assert "test_alpha" in body


def test_execute_flatten_converts_class_to_top_level(make_test_pkg):
    """AC10: flatten converts a Test* class to top-level functions in place."""
    pkg = make_test_pkg(
        {
            "tests/integration/test_x.py": (
                "class TestX:\n    def test_one(self):\n        assert True\n"
            ),
        }
    )
    source = pkg / "tests/integration/test_x.py"
    op = FileOp(
        kind="flatten",
        source=source,
        target=source,
        rationale="heterogeneous-class",
        source_rule="TEST_QUALITY_CLASS_FLAT",
        split_map={"TestX": []},
    )

    execute([op], pkg)

    text = source.read_text()
    assert "class TestX" not in text
