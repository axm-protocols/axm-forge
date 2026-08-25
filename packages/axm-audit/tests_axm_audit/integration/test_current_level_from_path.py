"""Split from ``test_shared_helpers_io.py``."""

from pathlib import Path

import pytest

from axm_audit.core.rules.test_quality._shared import current_level_from_path


@pytest.mark.parametrize(
    ("relative", "expected"),
    [
        pytest.param(("unit", "x", "test_a.py"), "unit", id="unit"),
        pytest.param(
            ("functional", "test_x.py"),
            "integration",
            id="integration_from_functional",
        ),
        pytest.param(("test_root.py",), "root", id="root"),
    ],
)
def test_current_level_from_path(
    tmp_path: Path, relative: tuple[str, ...], expected: str
) -> None:
    tests_dir = tmp_path / "tests"
    test_file = tests_dir.joinpath(*relative)
    assert current_level_from_path(test_file, tests_dir) == expected
