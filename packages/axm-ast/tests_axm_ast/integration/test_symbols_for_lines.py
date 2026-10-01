"""Changed bodies, imports and methods retain module-qualified seeds."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_ast.core.changed_lines import symbols_for_lines

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    ("interval", "expected"),
    [
        ((3, 1), ("tiny.ops.add",)),
        ((1, 1), ("tiny.ops.Counter", "tiny.ops.Counter.tick", "tiny.ops.add")),
        ((7, 1), ("tiny.ops.Counter", "tiny.ops.Counter.tick")),
        ((3, 0), ()),
    ],
)
def test_symbols_for_lines(tmp_path: Path, interval, expected):
    package = tmp_path / "src/tiny"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("")
    file = package / "ops.py"
    file.write_text(
        "from math import floor\n"
        "def add(x):\n    return floor(x) + 1\n\n"
        "class Counter:\n    def tick(self):\n        return 1\n"
    )
    assert symbols_for_lines(package, file, [interval]) == expected
