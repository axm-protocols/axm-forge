from __future__ import annotations

import subprocess
import sys
from unittest.mock import MagicMock

from axm_ast.tools.describe import DescribeTool


def test_describe_full_rejected():
    """detail='full' must be rejected with a clear error."""
    result = DescribeTool().execute(detail="full")

    assert result.success is False
    assert result.error is not None
    assert "detailed" in result.error.lower()
    assert "ast_inspect" in result.error.lower()


def test_describe_detailed_still_works(tmp_path, mocker):
    """detail='detailed' must still work and return modules."""
    pkg = MagicMock()
    pkg.modules = [MagicMock(), MagicMock()]

    mocker.patch(
        "axm_ast.core.cache.get_package",
        return_value=pkg,
    )
    mocker.patch(
        "axm_ast.formatters.filter_modules",
        return_value=pkg,
    )
    mocker.patch(
        "axm_ast.formatters.format_json",
        return_value={"modules": [{"name": "a"}, {"name": "b"}]},
    )

    result = DescribeTool().execute(path=str(tmp_path), detail="detailed")

    assert result.success is True
    assert result.data["module_count"] == 2
    assert len(result.data["modules"]) == 2


def test_cli_detail_full_rejected():
    """CLI --detail full must produce a clear error and exit 1."""
    proc = subprocess.run(
        [sys.executable, "-m", "axm_ast", "describe", "--detail", "full"],
        capture_output=True,
        text=True,
    )

    assert proc.returncode != 0
