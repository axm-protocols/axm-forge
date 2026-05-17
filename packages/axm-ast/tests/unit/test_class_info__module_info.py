"""Split from ``test_nodes.py``."""

from pathlib import Path

from axm_ast.models.nodes import ClassInfo, ModuleInfo


def test_public_classes_with_all() -> None:
    mod = ModuleInfo(
        path=Path("test.py"),
        classes=[
            ClassInfo(name="Public", line_start=1, line_end=30),
            ClassInfo(name="_Private", line_start=31, line_end=50),
        ],
        all_exports=["Public"],
    )
    assert len(mod.public_classes) == 1


def test_public_classes_no_all():
    mod = ModuleInfo(
        path=Path("test.py"),
        classes=[
            ClassInfo(name="Public", line_start=1, line_end=5),
            ClassInfo(name="_Private", line_start=6, line_end=10),
        ],
    )
    assert len(mod.public_classes) == 1
