from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

import libcst as cst
import pytest
from pytest_mock import MockerFixture

from axm_anvil.core.move import move_symbols
from tests.integration._helpers import (
    _write,
    _write_empty_new,
    _write_old_foo,
    _write_pyproject__from_move_cycle_detection,
)

pytestmark = pytest.mark.integration


def test_move_atomic_batch_edit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    src = tmp_path / "source.py"
    tgt = tmp_path / "target.py"
    src.write_text("from __future__ import annotations\n\nclass Foo:\n    pass\n")
    tgt.write_text("from __future__ import annotations\n")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='t'\n")

    calls: list[dict[str, Any]] = []

    def spy_batch_edit(*args: Any, **kwargs: Any) -> None:
        calls.append({"args": args, "kwargs": kwargs})
        ops = kwargs.get("operations") or (args[1] if len(args) > 1 else [])
        root = kwargs.get("path") or (args[0] if args else ".")
        for op in ops:
            if op.get("op") == "replace":
                full = Path(root) / op["file"]
                text = full.read_text()
                for e in op.get("edits", []):
                    text = text.replace(e["old"], e["new"])
                full.write_text(text)
            elif op.get("op") == "write":
                full = Path(root) / op["file"]
                full.write_text(op["content"])

    monkeypatch.setattr("axm_anvil.core.move.batch_edit", spy_batch_edit, raising=False)

    move_symbols(src, tgt, ["Foo"], dry_run=False)
    assert len(calls) == 1
    ops = calls[0]["kwargs"].get("operations") or calls[0]["args"][1]
    files = {op["file"] for op in ops}
    assert len(files) == 2


@pytest.fixture
def pkg_dir(tmp_path: Path) -> Path:
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    return pkg


def test_move_rewrites_module_import_caller(tmp_path: Path, pkg_dir: Path) -> None:
    (pkg_dir / "old.py").write_text("def Foo():\n    return 1\n")
    (pkg_dir / "new.py").write_text("")
    (pkg_dir / "caller.py").write_text("import pkg.old\n\npkg.old.Foo()\n")

    plan = move_symbols(
        pkg_dir / "old.py",
        pkg_dir / "new.py",
        ["Foo"],
        workspace_root=tmp_path,
    )

    caller = (pkg_dir / "caller.py").read_text()
    assert "import pkg.new" in caller
    assert "pkg.new.Foo()" in caller
    assert "import pkg.old" not in caller
    assert any(str(entry.file).endswith("caller.py") for entry in plan.callers_updated)


def test_move_rewrites_alias_import(tmp_path: Path, pkg_dir: Path) -> None:
    (pkg_dir / "old.py").write_text("def Foo():\n    return 1\n")
    (pkg_dir / "new.py").write_text("")
    (pkg_dir / "caller.py").write_text("import pkg.old as om\n\nom.Foo()\n")

    move_symbols(
        pkg_dir / "old.py",
        pkg_dir / "new.py",
        ["Foo"],
        workspace_root=tmp_path,
    )

    caller = (pkg_dir / "caller.py").read_text()
    assert "import pkg.new" in caller
    assert "pkg.new.Foo()" in caller
    assert "import pkg.old as om" not in caller


def test_move_preserves_old_import_when_still_used(
    tmp_path: Path, pkg_dir: Path
) -> None:
    (pkg_dir / "old.py").write_text(
        "def Foo():\n    return 1\n\n\ndef Bar():\n    return 2\n"
    )
    (pkg_dir / "new.py").write_text("")
    (pkg_dir / "caller.py").write_text(
        "import pkg.old\n\npkg.old.Foo()\npkg.old.Bar()\n"
    )

    move_symbols(
        pkg_dir / "old.py",
        pkg_dir / "new.py",
        ["Foo"],
        workspace_root=tmp_path,
    )

    caller = (pkg_dir / "caller.py").read_text()
    assert "import pkg.old" in caller
    assert "import pkg.new" in caller
    assert "pkg.new.Foo()" in caller
    assert "pkg.old.Bar()" in caller


def test_move_attribute_rewrite_preserves_method_chain(
    tmp_path: Path, pkg_dir: Path
) -> None:
    (pkg_dir / "old.py").write_text(
        "class Foo:\n    def validate(self):\n        return True\n"
    )
    (pkg_dir / "new.py").write_text("")
    (pkg_dir / "caller.py").write_text("import pkg.old\n\npkg.old.Foo().validate()\n")

    move_symbols(
        pkg_dir / "old.py",
        pkg_dir / "new.py",
        ["Foo"],
        workspace_root=tmp_path,
    )

    caller = (pkg_dir / "caller.py").read_text()
    assert "pkg.new.Foo().validate()" in caller


def test_move_mixed_from_and_module_imports_in_same_caller(
    tmp_path: Path, pkg_dir: Path
) -> None:
    (pkg_dir / "old.py").write_text(
        "def Foo():\n    return 1\n\n\ndef Bar():\n    return 2\n"
    )
    (pkg_dir / "new.py").write_text("")
    (pkg_dir / "caller.py").write_text(
        "from pkg.old import Bar\nimport pkg.old\n\npkg.old.Foo()\nBar()\n"
    )

    move_symbols(
        pkg_dir / "old.py",
        pkg_dir / "new.py",
        ["Foo", "Bar"],
        workspace_root=tmp_path,
    )

    caller = (pkg_dir / "caller.py").read_text()
    assert "from pkg.new import Bar" in caller
    assert "pkg.new.Foo()" in caller
    assert "from pkg.old import Bar" not in caller
    assert "import pkg.old\n" not in caller


FIXTURES = Path(__file__).parent / "fixtures"


def test_move_complex_fixture(tmp_path: Path) -> None:
    src = tmp_path / "source_complex.py"
    tgt = tmp_path / "target_complex.py"
    shutil.copy(FIXTURES / "source_complex.py", src)
    shutil.copy(FIXTURES / "target_complex.py", tgt)
    (tmp_path / "pyproject.toml").write_text("[project]\nname='t'\n")

    move_symbols(
        src,
        tgt,
        ["TestAnalyzeModuleUnit", "TestAnalyzePackageIntegration"],
        dry_run=False,
    )
    target_text = tgt.read_text()
    assert "class TestAnalyzeModuleUnit" in target_text
    assert "class TestAnalyzePackageIntegration" in target_text
    assert "from unittest.mock" in target_text
    assert "import pytest" in target_text
    assert "from mylib.core.models import ModuleInfo" in target_text
    assert "SAMPLE_PKG" in target_text

    source_text = src.read_text()
    assert "class StaysHere" in source_text


PYPROJECT = "[project]\nname='t'\n"


def _import_lines_for(target_text: str, name: str) -> list[str]:
    return [
        line
        for line in target_text.splitlines()
        if name in line and line.lstrip().startswith(("import ", "from "))
    ]


def test_move_skips_duplicate_when_target_imports_same_name_different_module(
    tmp_path: Path,
) -> None:
    src = tmp_path / "source.py"
    tgt = tmp_path / "target.py"
    src.write_text(
        "from __future__ import annotations\n"
        "from pkg.models import ClassInfo\n\n"
        "class Uses:\n"
        "    def run(self) -> ClassInfo:\n"
        "        return ClassInfo()\n"
    )
    tgt.write_text(
        "from __future__ import annotations\nfrom pkg.models.nodes import ClassInfo\n"
    )
    (tmp_path / "pyproject.toml").write_text(PYPROJECT)

    plan = move_symbols(src, tgt, ["Uses"], dry_run=False)
    target_text = tgt.read_text()

    # AC1: exactly one import line brings ClassInfo into scope.
    assert len(_import_lines_for(target_text, "ClassInfo")) == 1, target_text
    assert "from pkg.models import ClassInfo" not in target_text
    assert "from pkg.models.nodes import ClassInfo" in target_text

    # AC3: structured warning naming target/source modules.
    assert any(
        w == "redundant import: ClassInfo already imported from pkg.models.nodes;"
        " source had pkg.models"
        for w in plan.warnings
    ), plan.warnings

    # AC4: ruff check passes (no F811 -> no ruff warning surfaced).
    assert not any(w.startswith("ruff check exited") for w in plan.warnings), (
        plan.warnings
    )


def test_move_merges_into_existing_block_when_same_module(tmp_path: Path) -> None:
    src = tmp_path / "source.py"
    tgt = tmp_path / "target.py"
    src.write_text(
        "from __future__ import annotations\n"
        "from m import A, B\n\n"
        "class Uses:\n"
        "    def run(self) -> tuple[A, B]:\n"
        "        return A(), B()\n"
    )
    tgt.write_text("from __future__ import annotations\nfrom m import A\n")
    (tmp_path / "pyproject.toml").write_text(PYPROJECT)

    plan = move_symbols(src, tgt, ["Uses"], dry_run=False)
    target_text = tgt.read_text()

    # AC2: merged into a single 'from m import ...' block containing A and B.
    from_m_lines = [
        line
        for line in target_text.splitlines()
        if line.lstrip().startswith("from m import")
    ]
    assert len(from_m_lines) == 1, target_text
    assert "A" in from_m_lines[0] and "B" in from_m_lines[0]

    # AC2/AC4: no redundant-import warning when modules match.
    assert not any(w.startswith("redundant import:") for w in plan.warnings), (
        plan.warnings
    )


def test_move_skips_duplicate_when_target_uses_alias(tmp_path: Path) -> None:
    src = tmp_path / "source.py"
    tgt = tmp_path / "target.py"
    src.write_text(
        "from __future__ import annotations\n"
        "from a import Foo as Bar\n\n"
        "class Uses:\n"
        "    def run(self) -> Bar:\n"
        "        return Bar()\n"
    )
    tgt.write_text("from __future__ import annotations\nfrom a import Foo as Bar\n")
    (tmp_path / "pyproject.toml").write_text(PYPROJECT)

    plan = move_symbols(src, tgt, ["Uses"], dry_run=False)
    target_text = tgt.read_text()

    # AC1: alias-aware dedup -> still exactly one import line for Bar.
    assert target_text.count("from a import Foo as Bar") == 1, target_text
    assert not any(w.startswith("ruff check exited") for w in plan.warnings), (
        plan.warnings
    )


def test_move_emits_redundant_import_warning_per_name(tmp_path: Path) -> None:
    src = tmp_path / "source.py"
    tgt = tmp_path / "target.py"
    src.write_text(
        "from __future__ import annotations\n"
        "from pkg.models import ClassInfo, FunctionInfo\n\n"
        "class Uses:\n"
        "    def run(self) -> tuple[ClassInfo, FunctionInfo]:\n"
        "        return ClassInfo(), FunctionInfo()\n"
    )
    tgt.write_text(
        "from __future__ import annotations\n"
        "from pkg.models.nodes import ClassInfo, FunctionInfo\n"
    )
    (tmp_path / "pyproject.toml").write_text(PYPROJECT)

    plan = move_symbols(src, tgt, ["Uses"], dry_run=False)

    # AC3: one structured warning per overlapping name, naming both modules.
    redundant = [w for w in plan.warnings if w.startswith("redundant import:")]
    assert len(redundant) == 2, plan.warnings
    assert (
        "redundant import: ClassInfo already imported from pkg.models.nodes;"
        " source had pkg.models"
    ) in redundant
    assert (
        "redundant import: FunctionInfo already imported from pkg.models.nodes;"
        " source had pkg.models"
    ) in redundant


def test_move_no_ruff_warning_when_target_has_overlapping_imports(
    tmp_path: Path,
) -> None:
    src = tmp_path / "source.py"
    tgt = tmp_path / "target.py"
    src.write_text(
        "from __future__ import annotations\n"
        "from pkg.models import ClassInfo, FunctionInfo\n\n"
        "class Uses:\n"
        "    def run(self) -> tuple[ClassInfo, FunctionInfo]:\n"
        "        return ClassInfo(), FunctionInfo()\n"
    )
    tgt.write_text(
        "from __future__ import annotations\n"
        "from pkg.models.nodes import ClassInfo, FunctionInfo\n"
    )
    (tmp_path / "pyproject.toml").write_text(PYPROJECT)

    plan = move_symbols(src, tgt, ["Uses"], dry_run=False)

    # AC4: no F811 -> ruff check exits 0 -> no 'ruff check exited' warning.
    assert not any(w.startswith("ruff check exited") for w in plan.warnings), (
        plan.warnings
    )


def test_move_still_adds_genuinely_new_imports(tmp_path: Path) -> None:
    src = tmp_path / "source.py"
    tgt = tmp_path / "target.py"
    src.write_text(
        "from __future__ import annotations\n"
        "from pathlib import Path\n\n"
        "class Uses:\n"
        "    def run(self) -> Path:\n"
        "        return Path('x')\n"
    )
    tgt.write_text("from __future__ import annotations\nimport os\n\n_SEP = os.sep\n")
    (tmp_path / "pyproject.toml").write_text(PYPROJECT)

    plan = move_symbols(src, tgt, ["Uses"], dry_run=False)
    target_text = tgt.read_text()

    # AC1 regression: additive path still works for genuinely new imports.
    assert "from pathlib import Path" in target_text
    assert any("Path" in label for label in plan.imports_added), plan.imports_added
    assert not any(w.startswith("redundant import:") for w in plan.warnings), (
        plan.warnings
    )


def test_move_overload_group_full(tmp_path: Path) -> None:
    src = tmp_path / "source.py"
    tgt = tmp_path / "target.py"
    src.write_text(
        "from __future__ import annotations\n"
        "from typing import overload\n\n"
        "@overload\n"
        "def f(x: int) -> int: ...\n"
        "@overload\n"
        "def f(x: str) -> str: ...\n"
        "def f(x):\n    return x\n"
    )
    tgt.write_text("from __future__ import annotations\n")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='t'\n")

    move_symbols(src, tgt, ["f"], dry_run=False)
    target_text = tgt.read_text()

    module = cst.parse_module(target_text)
    func_defs = [
        n for n in module.body if isinstance(n, cst.FunctionDef) and n.name.value == "f"
    ]
    assert len(func_defs) == 3


def test_move_preserves_target_existing_symbols(tmp_path: Path) -> None:
    src = tmp_path / "source.py"
    tgt = tmp_path / "target.py"
    src.write_text("from __future__ import annotations\n\nclass Moved:\n    pass\n")
    original_target = (
        "from __future__ import annotations\n"
        "from pathlib import Path\n\n"
        "EXISTING = 1\n\n"
        "class AlreadyHere:\n    pass\n"
    )
    tgt.write_text(original_target)
    (tmp_path / "pyproject.toml").write_text("[project]\nname='t'\n")

    move_symbols(src, tgt, ["Moved"], dry_run=False)
    target_text = tgt.read_text()
    assert "class AlreadyHere" in target_text
    assert "EXISTING = 1" in target_text
    assert "from pathlib import Path" in target_text
    assert "class Moved" in target_text


def test_reexport_injects_line_in_source(tmp_path: Path, pkg_dir: Path) -> None:
    (pkg_dir / "old.py").write_text("def Foo():\n    return 1\n")
    (pkg_dir / "new.py").write_text("")

    move_symbols(
        pkg_dir / "old.py",
        pkg_dir / "new.py",
        ["Foo"],
        workspace_root=tmp_path,
        reexport=True,
    )

    source = (pkg_dir / "old.py").read_text()
    assert "from pkg.new import Foo" in source
    assert "# re-export for backwards compat" in source
    assert "def Foo" not in source


def test_reexport_leaves_callers_untouched(tmp_path: Path, pkg_dir: Path) -> None:
    (pkg_dir / "old.py").write_text("def Foo():\n    return 1\n")
    (pkg_dir / "new.py").write_text("")
    caller_text = "from pkg.old import Foo\n\nFoo()\n"
    (pkg_dir / "caller.py").write_text(caller_text)

    plan = move_symbols(
        pkg_dir / "old.py",
        pkg_dir / "new.py",
        ["Foo"],
        workspace_root=tmp_path,
        reexport=True,
    )

    assert (pkg_dir / "caller.py").read_text() == caller_text
    assert plan.callers_updated == []


def test_reexport_dry_run_includes_export_line(tmp_path: Path, pkg_dir: Path) -> None:
    (pkg_dir / "old.py").write_text("def Foo():\n    return 1\n")
    (pkg_dir / "new.py").write_text("")

    plan = move_symbols(
        pkg_dir / "old.py",
        pkg_dir / "new.py",
        ["Foo"],
        workspace_root=tmp_path,
        reexport=True,
        dry_run=True,
    )

    assert "from pkg.new import Foo" in plan.source_text_new
    assert "def Foo" in (pkg_dir / "old.py").read_text()


def test_reexport_atomic_single_batch_edit(
    tmp_path: Path, pkg_dir: Path, mocker: MockerFixture
) -> None:
    (pkg_dir / "old.py").write_text("def Foo():\n    return 1\n")
    (pkg_dir / "new.py").write_text("")

    spy = mocker.patch("axm_anvil.core.move.batch_edit")

    move_symbols(
        pkg_dir / "old.py",
        pkg_dir / "new.py",
        ["Foo"],
        workspace_root=tmp_path,
        reexport=True,
    )

    assert spy.call_count == 1
    call = spy.call_args
    args = call.args
    ops = args[1] if len(args) > 1 else call.kwargs["operations"]
    replace_ops = [op for op in ops if op["op"] == "replace"]
    assert len(replace_ops) == 2


def test_reexport_with_rename_raises(tmp_path: Path, pkg_dir: Path) -> None:
    (pkg_dir / "old.py").write_text("def Foo():\n    return 1\n")
    (pkg_dir / "new.py").write_text("")

    with pytest.raises(ValueError):
        move_symbols(
            pkg_dir / "old.py",
            pkg_dir / "new.py",
            ["Foo"],
            workspace_root=tmp_path,
            reexport=True,
            rename={"Foo": "Bar"},
        )


def test_move_ruff_postprocess_runs(tmp_path: Path) -> None:
    src = tmp_path / "source.py"
    tgt = tmp_path / "target.py"
    src.write_text(
        "from __future__ import annotations\n"
        "from pathlib import Path\n\n"
        "class Moves:\n"
        "    def run(self) -> Path:\n"
        "        return Path('x')\n"
    )
    tgt.write_text("from __future__ import annotations\n")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='t'\n")

    move_symbols(src, tgt, ["Moves"], dry_run=False)
    source_text = src.read_text()
    assert "from pathlib import Path" not in source_text


def test_move_ruff_failure_non_fatal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    src = tmp_path / "source.py"
    tgt = tmp_path / "target.py"
    src.write_text("from __future__ import annotations\n\nclass Foo:\n    pass\n")
    tgt.write_text("from __future__ import annotations\n")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='t'\n")

    original_run = subprocess.run

    def fake_run(cmd, *args, **kwargs):
        if cmd and isinstance(cmd, list) and cmd[0] == "ruff":
            return subprocess.CompletedProcess(
                args=cmd, returncode=1, stdout="", stderr="ruff boom"
            )
        return original_run(cmd, *args, **kwargs)

    monkeypatch.setattr(
        "axm_anvil.core.postprocess.subprocess.run", fake_run, raising=False
    )

    plan = move_symbols(src, tgt, ["Foo"], dry_run=False)
    assert plan.warnings
    assert any("ruff" in w.lower() for w in plan.warnings)


def test_move_shared_helpers_extract_raises(tmp_path):
    src = tmp_path / "src.py"
    tgt = tmp_path / "tgt.py"
    src.write_text("def foo():\n    return 1\n")
    tgt.write_text("")
    with pytest.raises(NotImplementedError, match="extract mode arrives in Phase 3"):
        move_symbols(
            src,
            tgt,
            ["foo"],
            shared_helpers="extract",
            dry_run=True,
            workspace_root=tmp_path,
        )


def test_move_shared_helpers_module_raises(tmp_path):
    src = tmp_path / "src.py"
    tgt = tmp_path / "tgt.py"
    src.write_text("def foo():\n    return 1\n")
    tgt.write_text("")
    with pytest.raises(NotImplementedError):
        move_symbols(
            src,
            tgt,
            ["foo"],
            shared_helpers_module="_helpers",
            dry_run=True,
            workspace_root=tmp_path,
        )


def _setup(tmp_path: Path) -> tuple[Path, Path]:
    src = tmp_path / "source.py"
    tgt = tmp_path / "target.py"
    shutil.copy(FIXTURES / "source.py", src)
    shutil.copy(FIXTURES / "target.py", tgt)
    (tmp_path / "pyproject.toml").write_text("[project]\nname='t'\n")
    return src, tgt


def test_move_simple_class(tmp_path: Path) -> None:
    src, tgt = _setup(tmp_path)
    plan = move_symbols(
        src, tgt, ["TestFilesystemInvalidation", "TestEdgeCases"], dry_run=False
    )
    assert "TestFilesystemInvalidation" in plan.moved_names
    assert "TestEdgeCases" in plan.moved_names

    target_text = tgt.read_text()
    assert "class TestFilesystemInvalidation" in target_text
    assert "class TestEdgeCases" in target_text
    cst.parse_module(target_text)

    source_text = src.read_text()
    assert "class TestFilesystemInvalidation" not in source_text
    assert "class TestEdgeCases" not in source_text


def _write_pyproject(root: Path) -> None:
    (root / "pyproject.toml").write_text(
        '[project]\nname = "mypkg"\nversion = "0.1.0"\n'
    )


def _setup_clean_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    _write_pyproject(tmp_path)
    pkg = tmp_path / "src" / "mypkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    a = pkg / "a.py"
    a.write_text("def Bar():\n    return 1\n\ndef Foo():\n    return 42\n")
    b = pkg / "b.py"
    b.write_text("def helper():\n    return 2\n")
    return tmp_path, a, b


def test_dry_run_no_writes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    called = {"count": 0}

    def fake_batch_edit(*args: object, **kwargs: object) -> None:
        called["count"] += 1

    monkeypatch.setattr(
        "axm_anvil.core.move.batch_edit", fake_batch_edit, raising=False
    )
    src = _write(tmp_path / "src.py", "class Foo:\n    pass\n")
    tgt = _write(tmp_path / "tgt.py", "")
    plan = move_symbols(src, tgt, ["Foo"], dry_run=True)
    assert called["count"] == 0
    assert plan is not None
    assert "Foo" in plan.moved_names


def test_move_rewrites_three_callers(workspace: Path) -> None:
    """AC1, AC2, AC5: three callers each get `pkg.old` -> `pkg.new` rewrite."""
    old = _write_old_foo(workspace)
    new = _write_empty_new(workspace)
    pkg = workspace / "src" / "pkg"
    for i in range(1, 4):
        (pkg / f"caller{i}.py").write_text(
            f"from pkg.old import Foo\n\ndef run{i}():\n    return Foo()\n"
        )

    plan = move_symbols(old, new, ["Foo"], workspace_root=workspace)

    for i in range(1, 4):
        text = (pkg / f"caller{i}.py").read_text()
        assert "from pkg.new import Foo" in text
        assert "pkg.old" not in text
    assert "def Foo" not in old.read_text()
    assert len(plan.callers_updated) == 3


def test_move_rewrites_caller_preserves_alias(workspace: Path) -> None:
    """AC3: alias `Foo as F` survives the rewrite; usage `F()` is untouched."""
    old = _write_old_foo(workspace)
    new = _write_empty_new(workspace)
    pkg = workspace / "src" / "pkg"
    caller = pkg / "caller.py"
    caller.write_text("from pkg.old import Foo as F\n\nF()\n")

    move_symbols(old, new, ["Foo"], workspace_root=workspace)

    text = caller.read_text()
    assert "from pkg.new import Foo as F" in text
    assert "F()" in text
    assert "pkg.old" not in text


def test_move_rewrites_partial_import_line(workspace: Path) -> None:
    """AC4: only the moved name is removed from a multi-name import line."""
    pkg = workspace / "src" / "pkg"
    old = pkg / "old.py"
    old.write_text("A = 1\ndef Foo():\n    return 1\nB = 2\n")
    new = _write_empty_new(workspace)
    caller = pkg / "caller.py"
    caller.write_text("from pkg.old import A, Foo, B\n\nFoo()\n")

    move_symbols(old, new, ["Foo"], workspace_root=workspace)

    text = caller.read_text()
    assert "from pkg.new import Foo" in text
    assert "from pkg.old import A, B" in text or "from pkg.old import B, A" in text
    assert "from pkg.old import A, Foo, B" not in text


def test_move_dry_run_populates_callers_without_writing(workspace: Path) -> None:
    """AC9: dry_run returns `callers_updated` but leaves disk untouched."""
    old = _write_old_foo(workspace)
    new = _write_empty_new(workspace)
    pkg = workspace / "src" / "pkg"
    (pkg / "caller1.py").write_text("from pkg.old import Foo\n\nFoo()\n")
    (pkg / "caller2.py").write_text("from pkg.old import Foo\n\nFoo()\n")

    original_old = old.read_text()
    original_new = new.read_text()
    original_c1 = (pkg / "caller1.py").read_text()
    original_c2 = (pkg / "caller2.py").read_text()

    plan = move_symbols(old, new, ["Foo"], dry_run=True, workspace_root=workspace)

    assert len(plan.callers_updated) == 2
    assert old.read_text() == original_old
    assert new.read_text() == original_new
    assert (pkg / "caller1.py").read_text() == original_c1
    assert (pkg / "caller2.py").read_text() == original_c2


def test_move_skips_caller_importing_from_unrelated_module(
    workspace: Path,
) -> None:
    """AC8: caller importing the name from another module is not rewritten."""
    old = _write_old_foo(workspace)
    new = _write_empty_new(workspace)
    pkg = workspace / "src" / "pkg"
    (pkg / "unrelated.py").write_text("def Foo():\n    return 'unrelated'\n")
    caller = pkg / "caller.py"
    caller_text = "from pkg.unrelated import Foo\n\nFoo()\n"
    caller.write_text(caller_text)

    plan = move_symbols(old, new, ["Foo"], workspace_root=workspace)

    assert caller.read_text() == caller_text
    assert plan.callers_updated == []


def test_check_mode_returns_plan_without_writing(tmp_path: Path) -> None:
    root, a, b = _setup_clean_fixture(tmp_path)
    a_before = a.read_bytes()
    b_before = b.read_bytes()

    plan = move_symbols(a, b, ["Foo"], workspace_root=root, check=True)

    assert plan is not None
    assert hasattr(plan, "callers_updated")
    assert a.read_bytes() == a_before
    assert b.read_bytes() == b_before


def test_move_allows_preexisting_cycle(tmp_path: Path) -> None:
    _write_pyproject__from_move_cycle_detection(tmp_path)
    pkg = tmp_path / "src" / "mypkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "x.py").write_text("from mypkg.y import Y\n\ndef X():\n    return Y()\n")
    (pkg / "y.py").write_text("from mypkg.x import X\n\ndef Y():\n    return 1\n")
    a = pkg / "a.py"
    a.write_text("def Bar():\n    return 1\n\ndef Foo():\n    return 42\n")
    b = pkg / "b.py"
    b.write_text("def helper():\n    return 2\n")

    plan = move_symbols(a, b, ["Foo"], workspace_root=tmp_path)
    assert "Foo" in plan.moved_names
    assert "def Foo" in b.read_text()
    assert "def Foo" not in a.read_text()


def test_move_cross_package_skips_cycle_check(tmp_path: Path) -> None:
    _write_pyproject__from_move_cycle_detection(tmp_path)
    (tmp_path / "src" / "pkg_a").mkdir(parents=True)
    (tmp_path / "src" / "pkg_b").mkdir(parents=True)
    (tmp_path / "src" / "pkg_a" / "__init__.py").write_text("")
    (tmp_path / "src" / "pkg_b" / "__init__.py").write_text("")
    x = tmp_path / "src" / "pkg_a" / "x.py"
    y = tmp_path / "src" / "pkg_b" / "y.py"
    x.write_text("def Bar():\n    return 1\n\ndef Foo():\n    return Bar()\n")
    y.write_text("def existing():\n    return 0\n")

    plan = move_symbols(x, y, ["Foo"], workspace_root=tmp_path)
    assert any(
        "Cross-package move" in w and "cycle detection skipped" in w
        for w in plan.warnings
    )


def test_transitive_constant_chain(tmp_path: Path) -> None:
    source = tmp_path / "source.py"
    target = tmp_path / "target.py"
    source.write_text(
        "from pathlib import Path\n"
        "\n"
        'BASE = Path("/tmp")\n'
        'SUB = BASE / "x"\n'
        "\n"
        "def moved_func():\n"
        "    return SUB\n"
    )
    target.write_text("")

    plan = move_symbols(
        source, target, ["moved_func"], dry_run=True, workspace_root=tmp_path
    )
    text = plan.target_text_new
    assert "BASE" in text
    assert "SUB" in text
    assert text.index("BASE") < text.index("SUB")


def test_transitive_helper_chain(tmp_path: Path) -> None:
    source = tmp_path / "source.py"
    target = tmp_path / "target.py"
    source.write_text(
        "def _b():\n"
        "    return 2\n"
        "\n"
        "def _a():\n"
        "    return _b()\n"
        "\n"
        "def moved():\n"
        "    return _a()\n"
    )
    target.write_text("")

    plan = move_symbols(
        source, target, ["moved"], dry_run=True, workspace_root=tmp_path
    )
    text = plan.target_text_new
    assert "def _a" in text
    assert "def _b" in text
    assert text.index("def _b") < text.index("def _a")


def test_helper_shared_stays_in_source(tmp_path: Path) -> None:
    source = tmp_path / "source.py"
    target = tmp_path / "target.py"
    source.write_text(
        "def _shared():\n"
        "    return 1\n"
        "\n"
        "def moved():\n"
        "    return _shared()\n"
        "\n"
        "def remaining():\n"
        "    return _shared()\n"
    )
    target.write_text("")

    plan = move_symbols(
        source, target, ["moved"], dry_run=True, workspace_root=tmp_path
    )
    assert "def _shared" in plan.target_text_new
    assert "def _shared" in plan.source_text_new


def test_helper_solo_removed_from_source(tmp_path: Path) -> None:
    source = tmp_path / "source.py"
    target = tmp_path / "target.py"
    source.write_text(
        "def _only():\n"
        "    return 1\n"
        "\n"
        "def moved():\n"
        "    return _only()\n"
        "\n"
        "def remaining():\n"
        "    return 42\n"
    )
    target.write_text("")

    plan = move_symbols(
        source, target, ["moved"], dry_run=True, workspace_root=tmp_path
    )
    assert "def _only" in plan.target_text_new
    assert "def _only" not in plan.source_text_new


def test_constant_orphan_removed_transitively(tmp_path: Path) -> None:
    source = tmp_path / "source.py"
    target = tmp_path / "target.py"
    source.write_text(
        "from pathlib import Path\n"
        "\n"
        'A = Path("/a")\n'
        'B = A / "x"\n'
        'C = B / "y"\n'
        "X = 1\n"
        "\n"
        "def moved():\n"
        "    return C\n"
        "\n"
        "def remaining():\n"
        "    return X\n"
    )
    target.write_text("")

    plan = move_symbols(
        source, target, ["moved"], dry_run=True, workspace_root=tmp_path
    )
    src_new = plan.source_text_new
    assert "A = Path" not in src_new
    assert "B = A" not in src_new
    assert "C = B" not in src_new
    assert "X = 1" in src_new


def test_constant_kept_if_used_by_remaining(tmp_path: Path) -> None:
    source = tmp_path / "source.py"
    target = tmp_path / "target.py"
    source.write_text(
        "A = 42\n\ndef moved():\n    return A\n\ndef remaining():\n    return A\n"
    )
    target.write_text("")

    plan = move_symbols(
        source, target, ["moved"], dry_run=True, workspace_root=tmp_path
    )
    assert "A = 42" in plan.target_text_new
    assert "A = 42" in plan.source_text_new


def test_future_annotations_preserved(tmp_path: Path) -> None:
    source = tmp_path / "source.py"
    target = tmp_path / "target.py"
    source.write_text(
        "from __future__ import annotations\n"
        "\n"
        "def moved():\n"
        "    return 1\n"
        "\n"
        "def remaining():\n"
        "    return 2\n"
    )
    target.write_text("")

    plan = move_symbols(
        source, target, ["moved"], dry_run=True, workspace_root=tmp_path
    )
    assert "from __future__ import annotations" in plan.source_text_new


def test_topo_order_in_target_file(tmp_path: Path) -> None:
    source = tmp_path / "source.py"
    target = tmp_path / "target.py"
    source.write_text(
        "from pathlib import Path\n"
        "\n"
        'BASE_DIR = Path("/tmp")\n'
        'SAMPLE_PKG = BASE_DIR / "pkg"\n'
        "\n"
        "def moved():\n"
        "    return SAMPLE_PKG\n"
    )
    target.write_text("")

    plan = move_symbols(
        source, target, ["moved"], dry_run=True, workspace_root=tmp_path
    )
    text = plan.target_text_new
    assert "BASE_DIR" in text
    assert "SAMPLE_PKG" in text
    lines = text.splitlines()
    base_line = next(
        i for i, line in enumerate(lines) if "BASE_DIR" in line and "=" in line
    )
    sample_line = next(
        i for i, line in enumerate(lines) if "SAMPLE_PKG" in line and "=" in line
    )
    assert base_line < sample_line


def test_complex_fixture_full_transitive(tmp_path: Path) -> None:
    source = tmp_path / "source_complex.py"
    target = tmp_path / "target_complex.py"
    source.write_text(
        "from __future__ import annotations\n"
        "\n"
        "from pathlib import Path\n"
        "\n"
        'BASE_DIR = Path("/tmp")\n'
        'SAMPLE_PKG = BASE_DIR / "pkg"\n'
        'CONFIG = {"k": 1}\n'
        'EXPECTED_MODULES = ["a", "b"]\n'
        "\n"
        "def _make_package():\n"
        "    return SAMPLE_PKG\n"
        "\n"
        "def _assert_valid_result(r):\n"
        "    assert r in EXPECTED_MODULES\n"
        "\n"
        "class TestAnalyzePackageIntegration:\n"
        "    def test_it(self):\n"
        "        pkg = _make_package()\n"
        '        _assert_valid_result("a")\n'
        "        cfg = CONFIG\n"
        "        return pkg, cfg\n"
        "\n"
        "def remaining():\n"
        "    return 0\n"
    )
    target.write_text("")

    plan = move_symbols(
        source,
        target,
        ["TestAnalyzePackageIntegration"],
        dry_run=True,
        workspace_root=tmp_path,
    )
    tgt = plan.target_text_new
    assert "BASE_DIR" in tgt
    assert "SAMPLE_PKG" in tgt
    assert "CONFIG" in tgt
    assert "EXPECTED_MODULES" in tgt
    assert "_make_package" in tgt
    assert "_assert_valid_result" in tgt
    assert tgt.index("BASE_DIR") < tgt.index("SAMPLE_PKG")

    src = plan.source_text_new
    assert "_make_package" not in src
    assert "_assert_valid_result" not in src
    assert "SAMPLE_PKG" not in src
    assert "BASE_DIR" not in src
    assert "def remaining" in src


def test_no_regression_simple_move(tmp_path: Path) -> None:
    source = tmp_path / "source.py"
    target = tmp_path / "target.py"
    source.write_text("def moved():\n    return 1\n\ndef remaining():\n    return 2\n")
    target.write_text("")

    plan = move_symbols(
        source, target, ["moved"], dry_run=True, workspace_root=tmp_path
    )
    assert "def moved" in plan.target_text_new
    assert "def moved" not in plan.source_text_new
    assert "def remaining" in plan.source_text_new


def test_move_with_direct_constants(tmp_path: Path) -> None:
    src = tmp_path / "source.py"
    tgt = tmp_path / "target.py"
    src.write_text(
        "from __future__ import annotations\n"
        "from pathlib import Path\n\n"
        "FIXTURES = Path('x')\n\n"
        "class Uses:\n"
        "    def run(self) -> Path:\n"
        "        return FIXTURES\n"
    )
    tgt.write_text("from __future__ import annotations\n")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='t'\n")

    plan = move_symbols(src, tgt, ["Uses"], dry_run=False)
    target_text = tgt.read_text()
    assert "FIXTURES" in target_text
    assert "class Uses" in target_text
    assert "FIXTURES" in plan.constants_added

    source_text = src.read_text()
    assert "class Uses" not in source_text


def test_move_with_direct_imports(tmp_path: Path) -> None:
    src = tmp_path / "source.py"
    tgt = tmp_path / "target.py"
    src.write_text(
        "from __future__ import annotations\n"
        "from pathlib import Path\n\n"
        "class Uses:\n"
        "    def run(self) -> None:\n"
        "        p = Path('x')\n"
        "        assert p\n"
    )
    tgt.write_text("from __future__ import annotations\n")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='t'\n")

    move_symbols(src, tgt, ["Uses"], dry_run=False)
    target_text = tgt.read_text()
    assert "from pathlib import Path" in target_text
    assert "class Uses" in target_text


@pytest.mark.integration
def test_shared_helper_duplicate_mode_default(shared_helper_fixture):
    root, source, target = shared_helper_fixture
    plan = move_symbols(source, target, ["moved_A"], workspace_root=root)
    assert "_shared" in target.read_text()
    assert "_shared" in source.read_text()
    assert any("Helper '_shared' is also used by" in w for w in plan.warnings)


@pytest.mark.integration
def test_shared_helper_duplicate_mode_explicit(shared_helper_fixture):
    root, source, target = shared_helper_fixture
    plan = move_symbols(
        source,
        target,
        ["moved_A"],
        shared_helpers="duplicate",
        workspace_root=root,
    )
    assert "_shared" in target.read_text()
    assert "_shared" in source.read_text()
    assert any("Helper '_shared' is also used by" in w for w in plan.warnings)


@pytest.mark.integration
def test_non_shared_helper_no_warning(tmp_path):
    source = tmp_path / "src.py"
    target = tmp_path / "tgt.py"
    source.write_text(
        "def _only_moved():\n"
        "    return 1\n"
        "\n"
        "def moved_A():\n"
        "    return _only_moved()\n"
        "\n"
        "def remaining_B():\n"
        "    return 2\n"
    )
    target.write_text("")
    plan = move_symbols(source, target, ["moved_A"], workspace_root=tmp_path)
    assert not any("also used by" in w for w in plan.warnings)
    assert "_only_moved" not in source.read_text()
    assert "_only_moved" in target.read_text()


@pytest.mark.integration
def test_transitive_shared_helper_detected(tmp_path):
    source = tmp_path / "src.py"
    target = tmp_path / "tgt.py"
    source.write_text(
        "def _a():\n"
        "    return 1\n"
        "\n"
        "def _b():\n"
        "    return _a()\n"
        "\n"
        "def moved_A():\n"
        "    return _a()\n"
        "\n"
        "def remaining_B():\n"
        "    return _b()\n"
    )
    target.write_text("")
    plan = move_symbols(source, target, ["moved_A"], workspace_root=tmp_path)
    assert "_a" in target.read_text()
    assert "_a" in source.read_text()
    assert any("Helper '_a' is also used by" in w for w in plan.warnings)
