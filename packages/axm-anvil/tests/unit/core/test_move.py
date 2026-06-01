from __future__ import annotations

import libcst as cst

from axm_anvil._cst.blocks import Block, extract_blocks
from axm_anvil.core.move import (
    PYTEST_BUILTIN_FIXTURES,
    detect_fixture_dependencies,
)


def _blocks_for(source: str, names: list[str]) -> list[Block]:
    """Parse ``source`` in memory and extract the requested top-level blocks."""
    return extract_blocks(cst.parse_module(source), names)


def test_builtin_fixture_never_warns() -> None:
    """AC1: a moved test using only the builtin ``tmp_path`` fixture is not
    flagged as a non-builtin fixture dependency (in-memory detection)."""
    assert "tmp_path" in PYTEST_BUILTIN_FIXTURES
    blocks = _blocks_for("def test_x(tmp_path):\n    return tmp_path\n", ["test_x"])

    used = detect_fixture_dependencies(blocks, local_names=set())

    assert "tmp_path" not in used
    assert used == set()


def test_fixture_usage_detected() -> None:
    """AC2: a moved ``def test_x(my_fixture)`` whose parameter is neither a
    builtin nor a locally-resolvable name is identified as a fixture
    dependency (in-memory detection, no filesystem I/O)."""
    blocks = _blocks_for("def test_x(my_fixture):\n    return my_fixture\n", ["test_x"])

    used = detect_fixture_dependencies(blocks, local_names=set())

    assert "my_fixture" in used


def test_fixture_param_resolvable_as_local_excluded() -> None:
    """AC2: a test parameter whose name is also a local/imported symbol is not
    treated as a fixture dependency."""
    blocks = _blocks_for("def test_x(helper):\n    return helper\n", ["test_x"])

    used = detect_fixture_dependencies(blocks, local_names={"helper"})

    assert "helper" not in used


def test_fixture_self_and_defaults_excluded() -> None:
    """AC2: ``self`` and parameters carrying a default are never fixtures."""
    blocks = _blocks_for(
        "class C:\n    def test_m(self, real_fixture, opt=1):\n"
        "        return real_fixture\n",
        ["C"],
    )

    used = detect_fixture_dependencies(blocks, local_names=set())

    assert "self" not in used
    assert "opt" not in used
