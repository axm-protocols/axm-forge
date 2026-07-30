from __future__ import annotations

from pathlib import Path

import pytest

from axm_anvil.core.plan import MoveValidationError
from axm_anvil.core.rename import rename_symbols

pytestmark = pytest.mark.integration


def test_rename_to_keyword_raises_validation_error(tmp_path: Path) -> None:
    """Renaming to a Python keyword produces unparseable code and raises
    MoveValidationError from the render/validate step."""
    mod = tmp_path / "mod.py"
    mod.write_text("def foo() -> int:\n    return 1\n")

    with pytest.raises(MoveValidationError):
        rename_symbols(
            tmp_path,
            "mod.py",
            {"foo": "def"},
            workspace_root=tmp_path,
        )
