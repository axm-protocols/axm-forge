"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from axm_ast.core.analyzer import analyze_package
from axm_ast.models.nodes import (
    ClassInfo,
    FunctionInfo,
    FunctionKind,
    ModuleInfo,
    PackageInfo,
    VariableInfo,
)
from tests.integration._helpers import (
    _write_pyproject,
    _write_src_module,
    _write_test_modules,
)


@pytest.fixture
def sample_data() -> dict[str, str]:
    """Provide sample test data."""
    return {"key": "value"}


@pytest.fixture()
def rich_pkg(tmp_path: Path) -> str:
    """Create a package with functions, classes, variables, and modules."""
    pkg = tmp_path / "richpkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text('"""Rich demo package."""\n')
    (pkg / "core.py").write_text(
        '"""Core module."""\n\n'
        'VERSION = "1.0.0"\n\n\n'
        "def greet(name: str) -> str:\n"
        '    """Say hello to someone.\n\n'
        "    Args:\n"
        "        name: The person to greet.\n\n"
        "    Returns:\n"
        "        A greeting string.\n"
        '    """\n'
        '    return f"Hello {name}"\n\n\n'
        "class Greeter:\n"
        '    """A greeting helper class."""\n\n'
        '    def __init__(self, prefix: str = "Hi") -> None:\n'
        "        self.prefix = prefix\n\n"
        "    def say_hello(self, name: str) -> str:\n"
        '        """Greet someone with a prefix.\n\n'
        "        Args:\n"
        "            name: The person to greet.\n\n"
        "        Returns:\n"
        "            A greeting string.\n"
        '        """\n'
        '        return f"{self.prefix} {name}"\n'
    )
    (pkg / "rich_mod.py").write_text(
        '"""A rich module with several symbols."""\n\n'
        "MAGIC = 42\n\n\n"
        "def helper() -> int:\n"
        '    """Return a magic number."""\n'
        "    return MAGIC\n\n\n"
        "class Widget:\n"
        '    """A widget."""\n\n'
        "    def run(self) -> None:\n"
        '        """Run the widget."""\n'
    )
    return str(pkg)


@pytest.fixture
def _fake_pkg() -> PackageInfo:
    """Build a minimal PackageInfo with modules and symbols."""
    method = FunctionInfo(
        name="do_stuff",
        line_start=10,
        line_end=15,
        signature="(self) -> None",
        params=[],
        return_type="None",
        docstring="method doc",
    )
    cls = ClassInfo(
        name="MyClass",
        line_start=5,
        line_end=20,
        docstring="class doc",
        bases=["Base"],
        methods=[method],
    )
    func = FunctionInfo(
        name="helper",
        line_start=25,
        line_end=30,
        signature="(x: int) -> str",
        params=[],
        return_type="str",
        docstring="helper doc",
    )
    from pathlib import Path

    mod = ModuleInfo(
        path=Path("/fake/src/mypkg/core.py"),
        name="core",
        docstring="core module",
        functions=[func],
        classes=[cls],
        variables=[],
        imports=[],
    )
    mod2 = ModuleInfo(
        path=Path("/fake/src/mypkg/sub/helpers.py"),
        name="sub.helpers",
        docstring="helpers module",
        functions=[],
        classes=[],
        variables=[],
        imports=[],
    )
    pkg = MagicMock(spec=PackageInfo)
    pkg.modules = [mod, mod2]
    pkg.module_names = ["core", "sub.helpers"]
    pkg.root = Path("/fake/src/mypkg")
    return pkg


@pytest.fixture
def pkg_with_tests(tmp_path: Path) -> PackageInfo:
    """Package with both src/ and tests/ directories."""
    pkg_dir = tmp_path / "my_pkg"
    pkg_dir.mkdir()
    _write_pyproject(pkg_dir, "my_pkg")
    _write_src_module(pkg_dir, "my_pkg")
    _write_test_modules(pkg_dir)
    return analyze_package(pkg_dir)


@pytest.fixture
def project_path(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture()
def rich_pkg__from_inspect(tmp_path: Path) -> Path:
    """Create a package with nested modules and classes for inspect tests."""
    pkg = tmp_path / "inspectdemo"
    pkg.mkdir()
    (pkg / "__init__.py").write_text('"""Inspect demo."""\n')
    (pkg / "core.py").write_text(
        '"""Core module."""\n\n'
        '__all__ = ["greet", "MyClass"]\n\n\n'
        "def greet(name: str) -> str:\n"
        '    """Say hello."""\n'
        '    return f"Hello {name}"\n\n\n'
        "class MyClass:\n"
        '    """A demo class."""\n\n'
        "    def my_method(self) -> None:\n"
        '        """Run method."""\n\n'
        "    @property\n"
        "    def label(self) -> str:\n"
        '        """Get label."""\n'
        '        return "label"\n'
    )
    sub = pkg / "sub"
    sub.mkdir()
    (sub / "__init__.py").write_text('"""Sub package."""\n')
    (sub / "helpers.py").write_text(
        '"""Helper module."""\n\n\n'
        "def helper_func() -> int:\n"
        '    """Help."""\n'
        "    return 42\n"
    )
    return pkg


@pytest.fixture()
def sample_project(tmp_path: Path) -> Path:
    """Create a minimal Python package for tool testing."""
    pkg = tmp_path / "src" / "demo"
    pkg.mkdir(parents=True)

    (pkg / "__init__.py").write_text(
        '"""Demo package."""\n\n__all__ = ["greet"]\n\nfrom demo.core import greet\n'
    )
    (pkg / "core.py").write_text(
        '"""Core module."""\n\n'
        '__all__ = ["greet", "Helper"]\n\n\n'
        "def greet(name: str) -> str:\n"
        '    """Say hello."""\n'
        '    return f"Hello {name}"\n\n\n'
        "class Helper:\n"
        '    """A helper class."""\n\n'
        "    def run(self) -> None:\n"
        '        """Run the helper."""\n'
        "        greet('world')\n\n"
        "    @property\n"
        "    def label(self) -> str:\n"
        '        """Helper label."""\n'
        '        return "helper"\n\n'
        "    @classmethod\n"
        "    def from_name(cls, name: str) -> 'Helper':\n"
        '        """Create from name."""\n'
        "        return cls()\n\n"
        "    @staticmethod\n"
        "    def version() -> str:\n"
        '        """Return version."""\n'
        '        return "1.0"\n'
    )

    # Add a pyproject.toml for context tool
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo"\nversion = "0.1.0"\n'
        'requires-python = ">=3.12"\n\n'
        "[build-system]\n"
        'requires = ["hatchling"]\n'
        'build-backend = "hatchling.build"\n'
    )

    # Add a README for docs tool
    (tmp_path / "README.md").write_text("# Demo\n\nA demo project.\n")

    return tmp_path


@pytest.fixture()
def simple_pkg(tmp_path: Path) -> Path:
    """Package with a simple function and no docstring."""
    pkg = tmp_path / "simplepkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text('"""Simple."""\n')
    (pkg / "core.py").write_text(
        "def greet(name):\n"
        "    return f'hello {name}'\n\n"
        "def helper():\n"
        "    return greet('world')\n"
    )
    (pkg / "wrapper.py").write_text(
        "from .core import greet\n\n"
        "def wrapped():\n"
        '    """Wrapped call."""\n'
        "    return greet('wrapped')\n"
    )
    return pkg


@pytest.fixture()
def src_tree(tmp_path: Path) -> Path:
    """Return *tmp_path* with a ``src/pkg/`` directory pre-created."""
    pkg = tmp_path / "src" / "pkg"
    pkg.mkdir(parents=True)
    return tmp_path


@pytest.fixture()
def typed_pkg(typed_project: Path) -> object:
    """Return analyzed package from typed_project."""
    return analyze_package(typed_project / "src" / "demo")


@pytest.fixture()
def typed_project(tmp_path: Path) -> Path:
    """Create a minimal package with type annotations."""
    pkg = tmp_path / "src" / "demo"
    pkg.mkdir(parents=True)

    (pkg / "__init__.py").write_text('"""Demo package."""\n\n__all__ = ["MyModel"]\n')
    (pkg / "models.py").write_text(
        '"""Models module."""\n\n'
        '__all__ = ["MyModel", "MyModelExtended"]\n\n\n'
        "class MyModel:\n"
        '    """A demo model."""\n\n'
        "    name: str\n\n\n"
        "class MyModelExtended:\n"
        '    """An extended model."""\n\n'
        "    name: str\n"
    )
    (pkg / "service.py").write_text(
        '"""Service module."""\n\n'
        '__all__ = ["process", "transform", "get_model",'
        ' "handle_optional", "handle_dict", "handle_list",'
        ' "handle_nested", "handle_string_ann"]\n\n\n'
        "def process(item: MyModel) -> str:\n"
        '    """Process a model."""\n'
        "    return item.name\n\n\n"
        "def transform(items: list[MyModel]) -> list[str]:\n"
        '    """Transform models."""\n'
        "    return [i.name for i in items]\n\n\n"
        "def get_model() -> MyModel:\n"
        '    """Return a model."""\n'
        "    return MyModel()\n\n\n"
        "def handle_optional(x: MyModel | None) -> None:\n"
        '    """Handle optional."""\n'
        "    pass\n\n\n"
        "def handle_dict(d: dict[str, MyModel]) -> None:\n"
        '    """Handle dict value."""\n'
        "    pass\n\n\n"
        "def handle_list(items: list[MyModel]) -> None:\n"
        '    """Handle list."""\n'
        "    pass\n\n\n"
        "def handle_nested(d: dict[str, list[MyModel]]) -> None:\n"
        '    """Handle nested generics."""\n'
        "    pass\n\n\n"
        'def handle_string_ann(x: "MyModel") -> None:\n'
        '    """Handle string annotation."""\n'
        "    pass\n\n\n"
        "def unrelated(x: OtherType) -> None:\n"
        '    """Unrelated function."""\n'
        "    pass\n\n\n"
        "def uses_extended(x: MyModelExtended) -> None:\n"
        '    """Uses extended model — should NOT match MyModel."""\n'
        "    pass\n"
    )
    (pkg / "aliases.py").write_text(
        '"""Aliases module."""\n\n'
        "__all__: list[str] = []\n\n"
        "ModelAlias: type = MyModel\n"
    )
    (pkg / "untyped.py").write_text(
        '"""Untyped module — no annotations."""\n\n'
        "__all__: list[str] = []\n\n\n"
        "def plain(x):\n"
        '    """No type annotations."""\n'
        "    return x\n"
    )

    # Add pyproject.toml
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo"\nversion = "0.1.0"\n'
        'requires-python = ">=3.12"\n\n'
        "[build-system]\n"
        'requires = ["hatchling"]\n'
        'build-backend = "hatchling.build"\n'
    )

    return tmp_path


@pytest.fixture()
def _patch_scan_classes_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch all helpers called by _scan_classes so we test its logic only."""
    monkeypatch.setattr(
        "axm_ast.core.dead_code._collect_base_class_names", lambda _pkg: set()
    )
    monkeypatch.setattr("axm_ast.core.callers.find_callers", lambda _pkg, _name: [])
    monkeypatch.setattr(
        "axm_ast.core.dead_code._is_exempt_class", lambda _cls, _mod: False
    )
    monkeypatch.setattr(
        "axm_ast.core.dead_code._has_intra_module_refs",
        lambda _name, _line, _mod: False,
    )
    monkeypatch.setattr(
        "axm_ast.core.dead_code._scan_methods",
        lambda _cls, _mod, _pkg, _ctx: [],
    )


@pytest.fixture()
def rich_pkg__from_analyzer() -> PackageInfo:
    """Package with functions, classes (with methods), and variables across modules."""
    mod_vars = ModuleInfo(
        path=Path("vars.py"),
        variables=[
            VariableInfo(name="MAX_RETRIES", annotation="int", value_repr="3", line=1),
            VariableInfo(name="TIMEOUT", annotation="float", value_repr="30.0", line=2),
            VariableInfo(name="_PRIVATE", annotation=None, value_repr="True", line=3),
        ],
    )
    mod_classes = ModuleInfo(
        path=Path("models.py"),
        classes=[
            ClassInfo(
                name="User",
                bases=["BaseModel"],
                line_start=1,
                line_end=10,
                methods=[
                    FunctionInfo(
                        name="validate",
                        kind=FunctionKind.METHOD,
                        return_type="bool",
                        line_start=5,
                        line_end=8,
                    ),
                ],
            ),
            ClassInfo(name="Admin", bases=["User"], line_start=12, line_end=20),
        ],
    )
    mod_mixed = ModuleInfo(
        path=Path("mixed.py"),
        functions=[
            FunctionInfo(
                name="greet",
                kind=FunctionKind.FUNCTION,
                return_type="str",
                line_start=1,
                line_end=3,
            ),
            FunctionInfo(
                name="compute",
                kind=FunctionKind.FUNCTION,
                return_type="int",
                line_start=5,
                line_end=7,
            ),
        ],
        classes=[
            ClassInfo(
                name="Parser",
                bases=[],
                line_start=10,
                line_end=30,
                methods=[
                    FunctionInfo(
                        name="parse",
                        kind=FunctionKind.METHOD,
                        return_type="str",
                        line_start=12,
                        line_end=15,
                    ),
                    FunctionInfo(
                        name="is_valid",
                        kind=FunctionKind.PROPERTY,
                        return_type="bool",
                        line_start=17,
                        line_end=20,
                    ),
                ],
            ),
        ],
        variables=[
            VariableInfo(name="VERSION", annotation="str", value_repr='"1.0"', line=35),
        ],
    )
    return PackageInfo(
        name="demo",
        root=Path("src/demo"),
        modules=[mod_vars, mod_classes, mod_mixed],
    )


@pytest.fixture()
def sample_class() -> ClassInfo:
    return ClassInfo(
        name="MyClass", line_start=10, line_end=20, bases=[], methods=[], decorators=[]
    )


@pytest.fixture()
def sample_func() -> FunctionInfo:
    return FunctionInfo(name="my_func", line_start=1, line_end=5, decorators=[])
