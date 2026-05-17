"""Split from ``test_nodes.py``."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from axm_ast.models.nodes import ModuleInfo


def test_empty_module():
    mod = ModuleInfo(path=Path("test.py"))
    assert mod.functions == []
    assert mod.classes == []
    assert mod.all_exports is None


def test_module_info_rejects_extra() -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        ModuleInfo(path=Path("x.py"), nope=1)  # type: ignore[call-arg]
