"""Split from ``test_nodes.py``."""

from pathlib import Path

from axm_ast.models.nodes import FunctionInfo, ModuleInfo, PackageInfo


def test_public_api() -> None:
    pkg = PackageInfo(
        name="test",
        root=Path("/test"),
        modules=[
            ModuleInfo(
                path=Path("/test/mod.py"),
                functions=[
                    FunctionInfo(name="pub", line_start=1, line_end=5),
                    FunctionInfo(name="_priv", line_start=6, line_end=10),
                ],
            )
        ],
    )
    api = pkg.public_api
    names = [s.name for s in api]
    assert "pub" in names
    assert "_priv" not in names
