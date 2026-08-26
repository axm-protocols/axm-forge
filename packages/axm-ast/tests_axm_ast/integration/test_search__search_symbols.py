from __future__ import annotations

from pathlib import Path

import pytest

from axm_ast import cli


@pytest.mark.integration
def test_search_prints_module_for_each_result(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """AC3: CLI search includes modules and distinguishes homonymous results."""
    package_dir = Path(__file__).parents[2]

    cli.search(path=str(package_dir), name="logger", kind="variable")

    output = capsys.readouterr().out
    result_lines = [line.strip() for line in output.splitlines() if "logger" in line]
    assert "axm_ast." in output
    assert len(result_lines) >= 2
    assert len(set(result_lines)) == len(result_lines)
