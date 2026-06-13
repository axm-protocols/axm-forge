from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

import libcst as cst
import pytest
from pytest_mock import MockerFixture

from axm_anvil.core.move import move_symbols
from axm_anvil.core.plan import MovePathError
from tests.integration._helpers import (
    SOURCE_WITH_METHOD,
    _write,
    _write_empty_new,
    _write_old_foo,
    _write_pyproject__from_move_cycle_detection,
    _write_workspace,
)

pytestmark = pytest.mark.integration


_NOOP_SOURCE = "def stayer() -> int:\n    return 1\n"


def test_noop_move_writes_nothing(tmp_path: Path) -> None:
    """AC1: a non-dry-run move where ALL requested symbols are absent
    (non-strict) writes NOTHING -- source and target files are byte-unchanged
    -- and returns a plan with moved_names == []."""
    src = tmp_path / "source.py"
    tgt = tmp_path / "target.py"
    src.write_text(_NOOP_SOURCE)
    tgt.write_text("")
    src_before = src.read_bytes()
    tgt_before = tgt.read_bytes()

    plan = move_symbols(src, tgt, ["ghost"], workspace_root=tmp_path)

    assert plan.moved_names == []
    assert src.read_bytes() == src_before
    assert tgt.read_bytes() == tgt_before


_PARTIAL_SOURCE = (
    'def present() -> int:\n    return 1\n\n\ndef stayer() -> str:\n    return "stay"\n'
)


def test_partial_move_still_moves_present(tmp_path: Path) -> None:
    """AC2: a move where SOME symbols are present still moves those present
    ones and leaves the rest (existing partial behavior unchanged)."""
    src = tmp_path / "source.py"
    tgt = tmp_path / "target.py"
    src.write_text(_PARTIAL_SOURCE)
    tgt.write_text("")

    plan = move_symbols(src, tgt, ["present", "ghost"], workspace_root=tmp_path)

    assert plan.moved_names == ["present"]
    after_src = src.read_text()
    after_tgt = tgt.read_text()
    assert "def present" not in after_src
    assert "def stayer" in after_src
    assert "def present" in after_tgt


_CONDITIONAL_SOURCE = (
    "try:\n"
    "    import fast_json as json\n"
    "except ImportError:\n"
    "    import json\n"
    "\n\n"
    "def encode(value):\n"
    "    return json.dumps(value)\n"
)


@pytest.mark.parametrize(
    "inspect",
    [
        pytest.param("target", id="block_copied_to_target"),
        pytest.param("source", id="not_removed_from_source"),
    ],
)
def test_conditional_import_guard_preserved(tmp_path: Path, inspect: str) -> None:
    """AC2,AC3: moving a symbol that uses a conditionally-imported name copies the
    entire try/except guard block into the target AND never auto-removes it from
    the source, even when no remaining source symbol references it."""
    src = tmp_path / "source.py"
    tgt = tmp_path / "target.py"
    src.write_text(_CONDITIONAL_SOURCE)
    tgt.write_text("")

    move_symbols(src, tgt, ["encode"], workspace_root=tmp_path)

    after = (tgt if inspect == "target" else src).read_text()
    assert "try:" in after
    assert "import fast_json as json" in after
    assert "except ImportError:" in after


_ORPHAN_CONDITIONAL_SOURCE = (
    "from __future__ import annotations\n"
    "\n"
    "try:\n"
    "    import tomllib\n"
    "except ModuleNotFoundError:\n"
    "    import tomli as tomllib\n"
    "\n\n"
    "def mover() -> int:\n"
    "    return 1\n"
    "\n\n"
    "def stayer() -> str:\n"
    '    return "no import use"\n'
)


def test_conditional_import_fallback_not_stripped_when_orphaned(
    tmp_path: Path,
) -> None:
    """AC3 regression: moving a symbol that does NOT use a conditional import,
    while NO remaining symbol uses it either, must leave the full guard intact.

    The post-move ruff F401 pass previously stripped the ``except`` fallback
    (``import tomli as tomllib``) down to ``pass`` because it was unused,
    silently changing runtime behavior. The fallback must survive verbatim.
    """
    src = tmp_path / "source.py"
    tgt = tmp_path / "target.py"
    src.write_text(_ORPHAN_CONDITIONAL_SOURCE)
    tgt.write_text("from __future__ import annotations\n")

    move_symbols(src, tgt, ["mover"], workspace_root=tmp_path)

    source_after = src.read_text()
    assert "try:" in source_after
    assert "import tomllib" in source_after
    assert "except ModuleNotFoundError:" in source_after
    # The fallback handler keeps its full import — not collapsed to ``pass``.
    assert "import tomli as tomllib" in source_after
    assert "except ModuleNotFoundError:\n    pass" not in source_after


def test_conditional_import_move_real_files(tmp_path: Path) -> None:
    """AC2,AC5: a real on-disk move into a target that already holds an
    equivalent guard block yields exactly one guard block (no duplicate)."""
    src = tmp_path / "source.py"
    tgt = tmp_path / "target.py"
    src.write_text(_CONDITIONAL_SOURCE)
    tgt.write_text(
        "try:\n"
        "    import fast_json as json\n"
        "except ImportError:\n"
        "    import json\n"
        "\n\n"
        "def existing():\n"
        '    return json.loads("{}")\n'
    )

    move_symbols(src, tgt, ["encode"], workspace_root=tmp_path)

    target_after = tgt.read_text()
    assert target_after.count("except ImportError:") == 1


_SOURCE = """\
from __future__ import annotations


def _helper(x: int) -> int:
    return x + 1


def public_fn(y: int) -> int:
    return _helper(y) * 2
"""

_TARGET = """\
from __future__ import annotations
"""


def _setup(tmp_path: Path) -> tuple[Path, Path]:
    src = tmp_path / "src_mod.py"
    tgt = tmp_path / "tgt_mod.py"
    src.write_text(_SOURCE)
    tgt.write_text(_TARGET)
    return src, tgt


def test_include_helpers_true_copies_helper(tmp_path: Path) -> None:
    """AC1: default ``include_helpers=True`` copies referenced local helper."""
    src, tgt = _setup(tmp_path)
    plan = move_symbols(src, tgt, ["public_fn"], dry_run=True, include_helpers=True)
    assert "def _helper" in plan.target_text_new


def test_include_helpers_false_skips_and_warns(tmp_path: Path) -> None:
    """AC2,AC3: ``include_helpers=False`` skips helper and warns by name."""
    src, tgt = _setup(tmp_path)
    plan = move_symbols(src, tgt, ["public_fn"], dry_run=True, include_helpers=False)
    assert "def _helper" not in plan.target_text_new
    assert any("_helper" in w for w in plan.warnings)


def test_all_removed_from_source(tmp_path: Path) -> None:
    """AC1: a moved symbol present in source `__all__` is removed from it."""
    src = _write(
        tmp_path / "src_mod.py",
        '__all__ = ["Foo", "Bar"]\n\n'
        "def Foo():\n    return 1\n\n"
        "def Bar():\n    return 2\n",
    )
    tgt = _write(tmp_path / "tgt_mod.py", '__all__ = ["Baz"]\n')
    plan = move_symbols(src, tgt, ["Foo"], dry_run=True)
    assert '"Foo"' not in plan.source_text_new
    assert '"Bar"' in plan.source_text_new


def test_all_added_to_existing_target(tmp_path: Path) -> None:
    """AC2: when target already declares `__all__`, the moved name is appended."""
    src = _write(
        tmp_path / "src_mod.py",
        '__all__ = ["Foo"]\n\ndef Foo():\n    return 1\n',
    )
    tgt = _write(tmp_path / "tgt_mod.py", '__all__ = ["Baz"]\n')
    plan = move_symbols(src, tgt, ["Foo"], dry_run=True)
    assert '"Foo"' in plan.target_text_new
    assert '"Baz"' in plan.target_text_new


def test_all_not_created_when_absent(tmp_path: Path) -> None:
    """AC3: no `__all__` is created on either side when absent."""
    src = _write(
        tmp_path / "src_mod.py",
        "def Foo():\n    return 1\n",
    )
    tgt = _write(tmp_path / "tgt_mod.py", "X = 1\n")
    plan = move_symbols(src, tgt, ["Foo"], dry_run=True)
    assert "__all__" not in plan.source_text_new
    assert "__all__" not in plan.target_text_new


def test_all_untouched_for_unexported_symbol(tmp_path: Path) -> None:
    """AC4: moving a symbol absent from source `__all__` leaves both untouched."""
    src = _write(
        tmp_path / "src_mod.py",
        '__all__ = ["Bar"]\n\ndef Foo():\n    return 1\n\ndef Bar():\n    return 2\n',
    )
    tgt = _write(tmp_path / "tgt_mod.py", '__all__ = ["Baz"]\n')
    plan = move_symbols(src, tgt, ["Foo"], dry_run=True)
    assert '__all__ = ["Bar"]' in plan.source_text_new
    assert '__all__ = ["Baz"]' in plan.target_text_new


def test_all_preserves_remaining_order(tmp_path: Path) -> None:
    """AC5: remaining `__all__` element order/formatting is preserved."""
    src = _write(
        tmp_path / "src_mod.py",
        '__all__ = ["A", "Foo", "B"]\n\n'
        "def A():\n    return 1\n\n"
        "def Foo():\n    return 2\n\n"
        "def B():\n    return 3\n",
    )
    tgt = _write(tmp_path / "tgt_mod.py", '__all__ = ["Z"]\n')
    plan = move_symbols(src, tgt, ["Foo"], dry_run=True)
    assert '__all__ = ["A", "B"]' in plan.source_text_new


FIXTURES = Path(__file__).parent / "fixtures"


PYPROJECT = "[project]\nname='t'\n"


@pytest.fixture
def pkg_dir(tmp_path: Path) -> Path:
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    return pkg


def _import_lines_for(target_text: str, name: str) -> list[str]:
    return [
        line
        for line in target_text.splitlines()
        if name in line and line.lstrip().startswith(("import ", "from "))
    ]


def _setup__from_move_symbols(tmp_path: Path) -> tuple[Path, Path]:
    src = tmp_path / "source.py"
    tgt = tmp_path / "target.py"
    shutil.copy(FIXTURES / "source.py", src)
    shutil.copy(FIXTURES / "target.py", tgt)
    (tmp_path / "pyproject.toml").write_text("[project]\nname='t'\n")
    return src, tgt


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


def _make_pkg(root: Path, name: str) -> Path:
    """Create ``root/name`` as an importable package dir with ``__init__.py``."""
    pkg = root / name
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "__init__.py").write_text("")
    return pkg


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


def test_move_rewrites_multiline_from_import_caller(
    tmp_path: Path, pkg_dir: Path
) -> None:
    """AC1: a caller importing the moved symbol via a multi-line
    ``from pkg.old import (\\n Foo,\\n)`` is discovered and redirected to pkg.new."""
    (pkg_dir / "old.py").write_text("def Foo():\n    return 1\n")
    (pkg_dir / "new.py").write_text("")
    (pkg_dir / "caller.py").write_text("from pkg.old import (\n    Foo,\n)\n\nFoo()\n")

    plan = move_symbols(
        pkg_dir / "old.py",
        pkg_dir / "new.py",
        ["Foo"],
        workspace_root=tmp_path,
    )

    caller = (pkg_dir / "caller.py").read_text()
    assert "from pkg.new import Foo" in caller
    assert "from pkg.old import" not in caller
    assert any(str(entry.file).endswith("caller.py") for entry in plan.callers_updated)


def test_move_multiline_caller_with_reexport(tmp_path: Path, pkg_dir: Path) -> None:
    """AC3: with ``reexport=True`` a multi-line caller is left untouched while the
    source keeps a re-export line; the caller file still parses."""
    (pkg_dir / "old.py").write_text("def Foo():\n    return 1\n")
    (pkg_dir / "new.py").write_text("")
    caller_text = "from pkg.old import (\n    Foo,\n)\n\nFoo()\n"
    (pkg_dir / "caller.py").write_text(caller_text)

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
    # reexport leaves callers untouched; the file still parses.
    caller = (pkg_dir / "caller.py").read_text()
    assert caller == caller_text
    cst.parse_module(caller)


def test_move_still_rewrites_module_import_caller(
    tmp_path: Path, pkg_dir: Path
) -> None:
    """AC2 regression: an ``import pkg.old`` caller is still discovered and
    rewritten after the CST discovery change."""
    (pkg_dir / "old.py").write_text("def Foo():\n    return 1\n")
    (pkg_dir / "new.py").write_text("")
    (pkg_dir / "caller.py").write_text("import pkg.old\n\npkg.old.Foo()\n")

    move_symbols(
        pkg_dir / "old.py",
        pkg_dir / "new.py",
        ["Foo"],
        workspace_root=tmp_path,
    )

    caller = (pkg_dir / "caller.py").read_text()
    assert "import pkg.new" in caller
    assert "pkg.new.Foo()" in caller
    assert "import pkg.old" not in caller


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
        if cmd and isinstance(cmd, list) and "ruff" in cmd:
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


def test_move_simple_class(tmp_path: Path) -> None:
    src, tgt = _setup__from_move_symbols(tmp_path)
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


@pytest.mark.parametrize(
    ("source_code", "moved", "first", "second"),
    [
        pytest.param(
            "from pathlib import Path\n"
            "\n"
            'BASE = Path("/tmp")\n'
            'SUB = BASE / "x"\n'
            "\n"
            "def moved_func():\n"
            "    return SUB\n",
            "moved_func",
            "BASE",
            "SUB",
            id="constant_chain",
        ),
        pytest.param(
            "def _b():\n"
            "    return 2\n"
            "\n"
            "def _a():\n"
            "    return _b()\n"
            "\n"
            "def moved():\n"
            "    return _a()\n",
            "moved",
            "def _b",
            "def _a",
            id="helper_chain",
        ),
    ],
)
def test_transitive_dependency_chain_topo_ordered(
    tmp_path: Path, source_code: str, moved: str, first: str, second: str
) -> None:
    """A moved symbol drags its transitive dependency chain into the target in
    topological order (the dependency appears before its dependent)."""
    source = tmp_path / "source.py"
    target = tmp_path / "target.py"
    source.write_text(source_code)
    target.write_text("")

    plan = move_symbols(source, target, [moved], dry_run=True, workspace_root=tmp_path)
    text = plan.target_text_new
    assert first in text
    assert second in text
    assert text.index(first) < text.index(second)


@pytest.mark.parametrize(
    ("source_code", "dep"),
    [
        pytest.param(
            "def _shared():\n"
            "    return 1\n"
            "\n"
            "def moved():\n"
            "    return _shared()\n"
            "\n"
            "def remaining():\n"
            "    return _shared()\n",
            "def _shared",
            id="shared_helper",
        ),
        pytest.param(
            "A = 42\n\ndef moved():\n    return A\n\ndef remaining():\n    return A\n",
            "A = 42",
            id="shared_constant",
        ),
    ],
)
def test_shared_dependency_kept_in_both_source_and_target(
    tmp_path: Path, source_code: str, dep: str
) -> None:
    """A dependency referenced by both the moved symbol and a remaining symbol is
    duplicated: it is copied into the target AND kept in the source."""
    source = tmp_path / "source.py"
    target = tmp_path / "target.py"
    source.write_text(source_code)
    target.write_text("")

    plan = move_symbols(
        source, target, ["moved"], dry_run=True, workspace_root=tmp_path
    )
    assert dep in plan.target_text_new
    assert dep in plan.source_text_new


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


def test_move_skips_method_name_with_warning(tmp_path: Path) -> None:
    """AC1, AC2: a class-method name is skipped+warned; the real symbol still moves."""
    source = tmp_path / "source_mod.py"
    target = tmp_path / "target_mod.py"
    source.write_text(SOURCE_WITH_METHOD)
    target.write_text('"""Target module."""\n')

    plan = move_symbols(
        source,
        target,
        ["test_basic", "real_toplevel"],
        workspace_root=tmp_path,
    )

    # The genuine top-level symbol moved.
    assert "real_toplevel" in plan.moved_names
    assert "def real_toplevel" in target.read_text()
    # The method name was not moved, and surfaced as a warning, not an exception.
    assert "test_basic" not in plan.moved_names
    assert any("test_basic" in w for w in plan.warnings)


def test_move_skip_in_check_mode_does_not_mutate(tmp_path: Path) -> None:
    """AC2: a dry_run surfaces the skip as a warning without writing files."""
    source = tmp_path / "source_mod.py"
    target = tmp_path / "target_mod.py"
    source.write_text(SOURCE_WITH_METHOD)
    target.write_text('"""Target module."""\n')
    source_before = source.read_text()
    target_before = target.read_text()

    plan = move_symbols(
        source,
        target,
        ["test_basic", "real_toplevel"],
        dry_run=True,
        workspace_root=tmp_path,
    )

    # Files untouched...
    assert source.read_text() == source_before
    assert target.read_text() == target_before
    # ...and the skip is still reported.
    assert any("test_basic" in w for w in plan.warnings)


def test_insert_after_places_block_after_anchor(tmp_path: Path) -> None:
    """AC1: the moved block is inserted right after the named anchor and before
    the symbol that originally followed the anchor in the target module."""
    from axm_anvil.core.move import move_symbols

    src = tmp_path / "source.py"
    tgt = tmp_path / "target.py"
    src.write_text("def Moved():\n    return 1\n")
    tgt.write_text("def Anchor():\n    return 0\n\n\ndef After():\n    return 2\n")

    move_symbols(src, tgt, ["Moved"], insert_after="Anchor")

    text = tgt.read_text()
    assert text.index("def Anchor") < text.index("def Moved") < text.index("def After")


def test_string_forward_ref_warns(tmp_path: Path) -> None:
    """AC1,AC2: moving `Foo` warns about a string annotation that references it."""
    from axm_anvil.core.move import move_symbols

    src = tmp_path / "source.py"
    tgt = tmp_path / "target.py"
    src.write_text('def Foo():\n    return 1\n\n\ndef g(x: "Foo"):\n    return x\n')
    tgt.write_text("")

    plan = move_symbols(src, tgt, ["Foo"], dry_run=True)

    assert any("Foo" in w for w in plan.warnings)


def test_string_forward_ref_no_false_positive(tmp_path: Path) -> None:
    """AC4: a string annotation `\"FooBar\"` does not trigger a forward-ref warning
    when only `Foo` is moved."""
    from axm_anvil.core.move import move_symbols

    src = tmp_path / "source.py"
    tgt = tmp_path / "target.py"
    src.write_text('def Foo():\n    return 1\n\n\ndef g(x: "FooBar"):\n    return x\n')
    tgt.write_text("")

    plan = move_symbols(src, tgt, ["Foo"], dry_run=True)

    assert not any("forward-reference" in w for w in plan.warnings)


def test_string_forward_ref_not_rewritten(tmp_path: Path) -> None:
    """AC3: detection-only — the literal string annotation is left untouched."""
    from axm_anvil.core.move import move_symbols

    src = tmp_path / "source.py"
    tgt = tmp_path / "target.py"
    src.write_text('def Foo():\n    return 1\n\n\ndef g(x: "Foo"):\n    return x\n')
    tgt.write_text("")

    plan = move_symbols(src, tgt, ["Foo"], dry_run=True)

    assert '"Foo"' in plan.source_text_new


def test_rename_propagates_to_target_dunder_all(tmp_path: Path) -> None:
    """Rename + __all__ sync: the target __all__ append uses the NEW name."""
    from axm_anvil.core.move import move_symbols

    src = tmp_path / "src_pkg.py"
    tgt = tmp_path / "tgt_pkg.py"
    src.write_text(
        '__all__ = ["Widget", "keep_me"]\n\n'
        "class Widget:\n    pass\n\n"
        "def keep_me():\n    return 1\n",
    )
    tgt.write_text('__all__ = ["existing"]\n\ndef existing():\n    return 0\n')

    move_symbols(
        src, tgt, ["Widget"], rename={"Widget": "Gadget"}, workspace_root=tmp_path
    )

    target_after = tgt.read_text()
    assert '"Gadget"' in target_after
    assert '"Widget"' not in target_after
    assert '"existing"' in target_after
    # source removal still keys on the original exported name
    assert '"Widget"' not in src.read_text()


def test_rename_rewrites_string_forward_ref_in_moved_code(tmp_path: Path) -> None:
    """Rename + string annotation: a moved "OldName" forward-ref becomes "NewName"."""
    from axm_anvil.core.move import move_symbols

    src = tmp_path / "source.py"
    tgt = tmp_path / "target.py"
    src.write_text(
        "class Widget:\n    pass\n\n\n"
        'def make_widget(spec: "Widget") -> "Widget":\n    return Widget()\n'
    )
    tgt.write_text("")

    plan = move_symbols(
        src,
        tgt,
        ["Widget", "make_widget"],
        rename={"Widget": "Gadget"},
        dry_run=True,
    )

    assert '"Gadget"' in plan.target_text_new
    assert '"Widget"' not in plan.target_text_new
    # the renamed forward-ref no longer warrants a manual-update warning
    assert not any("forward-reference 'Widget'" in w for w in plan.warnings)


def test_forward_ref_warning_real_files(tmp_path: Path) -> None:
    """AC1: a real on-disk move surfaces a non-empty warning naming the symbol."""
    from axm_anvil.core.move import move_symbols

    src = tmp_path / "source.py"
    tgt = tmp_path / "target.py"
    src.write_text('def Foo():\n    return 1\n\n\ndef g(x: "Foo"):\n    return x\n')
    tgt.write_text("")

    plan = move_symbols(src, tgt, ["Foo"], workspace_root=tmp_path)

    assert plan.warnings
    assert any("Foo" in w for w in plan.warnings)


def test_all_sync_real_files(tmp_path: Path) -> None:
    """AC1,AC2: written files reflect the synced `__all__` after a real move."""
    from axm_anvil.core.move import move_symbols

    src = tmp_path / "src_pkg.py"
    tgt = tmp_path / "tgt_pkg.py"
    src.write_text(
        '__all__ = ["Foo", "Bar"]\n\n'
        "def Foo():\n    return 1\n\n"
        "def Bar():\n    return 2\n",
    )
    tgt.write_text('__all__ = ["Existing"]\n\ndef Existing():\n    return 0\n')

    move_symbols(src, tgt, ["Foo"], workspace_root=tmp_path)

    source_after = src.read_text()
    target_after = tgt.read_text()
    assert '"Foo"' not in source_after
    assert '"Bar"' in source_after
    assert '"Foo"' in target_after
    assert '"Existing"' in target_after


def test_side_effect_decorator_dotted_warns(tmp_path: Path) -> None:
    """AC2, AC4: moving an ``@app.route("/x")`` fn warns, naming deco + symbol."""
    from axm_anvil.core.move import move_symbols

    src = tmp_path / "source.py"
    tgt = tmp_path / "target.py"
    src.write_text('import app\n\n\n@app.route("/x")\ndef handler():\n    return 1\n')
    tgt.write_text("")

    plan = move_symbols(src, tgt, ["handler"], dry_run=True)

    matching = [w for w in plan.warnings if "side-effect decorator" in w]
    assert matching, plan.warnings
    assert any("app.route" in w and "handler" in w for w in matching)


def test_side_effect_decorator_bare_warns(tmp_path: Path) -> None:
    """AC4: a bare whitelisted decorator (``@fixture``) emits a warning."""
    from axm_anvil.core.move import move_symbols

    src = tmp_path / "source.py"
    tgt = tmp_path / "target.py"
    src.write_text(
        "from pytest import fixture\n\n\n@fixture\ndef thing():\n    return 1\n"
    )
    tgt.write_text("")

    plan = move_symbols(src, tgt, ["thing"], dry_run=True)

    assert any(
        "side-effect decorator" in w and "fixture" in w and "thing" in w
        for w in plan.warnings
    ), plan.warnings


def test_non_whitelisted_decorator_no_warn(tmp_path: Path) -> None:
    """AC5: a non-whitelisted decorator produces no side-effect warning."""
    from axm_anvil.core.move import move_symbols

    src = tmp_path / "source.py"
    tgt = tmp_path / "target.py"
    src.write_text(
        "def deco(f):\n    return f\n\n\n@deco\ndef thing():\n    return 1\n"
    )
    tgt.write_text("")

    plan = move_symbols(src, tgt, ["thing"], dry_run=True)

    assert not any("side-effect decorator" in w for w in plan.warnings), plan.warnings


def test_custom_side_effect_decorator_extension(tmp_path: Path) -> None:
    """AC3: a caller-supplied custom decorator extends the whitelist."""
    from axm_anvil.core.move import move_symbols

    src = tmp_path / "source.py"
    tgt = tmp_path / "target.py"
    src.write_text("import mylib\n\n\n@mylib.register\ndef thing():\n    return 1\n")
    tgt.write_text("")

    plan = move_symbols(
        src,
        tgt,
        ["thing"],
        dry_run=True,
        side_effect_decorators=frozenset({"mylib.register"}),
    )

    assert any(
        "side-effect decorator" in w and "mylib.register" in w and "thing" in w
        for w in plan.warnings
    ), plan.warnings


def test_side_effect_decorator_warning_real_files(tmp_path: Path) -> None:
    """AC2: real-file move surfaces the decorator warning on plan.warnings."""
    from axm_anvil.core.move import move_symbols

    src = tmp_path / "app_routes.py"
    tgt = tmp_path / "tasks.py"
    src.write_text("import celery\n\n\n@celery.task\ndef do_work():\n    return 42\n")
    tgt.write_text("")

    plan = move_symbols(src, tgt, ["do_work"], workspace_root=tmp_path)

    assert any(
        "side-effect decorator" in w and "celery.task" in w and "do_work" in w
        for w in plan.warnings
    ), plan.warnings


def test_relative_import_intra_package_preserved(tmp_path: Path) -> None:
    """AC1: a relative import copied during an intra-package move is preserved
    as a relative import (source & target live in the same package)."""
    from axm_anvil.core.move import move_symbols

    pkg = _make_pkg(tmp_path, "pkg")
    (pkg / "helper.py").write_text("VALUE = 1\n")
    src = pkg / "source.py"
    tgt = pkg / "target.py"
    src.write_text("from . import helper\n\n\ndef Moved():\n    return helper.VALUE\n")
    tgt.write_text("")

    move_symbols(src, tgt, ["Moved"], workspace_root=tmp_path)

    target_after = tgt.read_text()
    assert "from . import helper" in target_after
    assert "pkg.helper" not in target_after


def test_relative_import_cross_package_converted(tmp_path: Path) -> None:
    """AC2,AC5: a relative import copied during a cross-package move is rewritten
    to the equivalent absolute import, preserving the imported name and alias."""
    from axm_anvil.core.move import move_symbols

    src_pkg = _make_pkg(tmp_path, "src_pkg")
    (src_pkg / "utils.py").write_text("def f():\n    return 1\n")
    dst_pkg = _make_pkg(tmp_path, "dst_pkg")
    src = src_pkg / "source.py"
    tgt = dst_pkg / "target.py"
    src.write_text("from .utils import f as g\n\n\ndef Moved():\n    return g()\n")
    tgt.write_text("")

    move_symbols(src, tgt, ["Moved"], workspace_root=tmp_path)

    target_after = tgt.read_text()
    assert "from src_pkg.utils import f as g" in target_after
    assert "from .utils" not in target_after


def test_absolute_import_untouched(tmp_path: Path) -> None:
    """AC3: an absolute import used by the moved code is copied unchanged."""
    from axm_anvil.core.move import move_symbols

    src_pkg = _make_pkg(tmp_path, "src_pkg")
    dst_pkg = _make_pkg(tmp_path, "dst_pkg")
    src = src_pkg / "source.py"
    tgt = dst_pkg / "target.py"
    src.write_text("import os\n\n\ndef Moved():\n    return os.getcwd()\n")
    tgt.write_text("")

    move_symbols(src, tgt, ["Moved"], workspace_root=tmp_path)

    target_after = tgt.read_text()
    assert "import os" in target_after


def test_unresolvable_relative_import_warns(tmp_path: Path) -> None:
    """AC4: a relative import that walks beyond the package root yields a
    structured warning and no malformed import is written to the target."""
    from axm_anvil.core.move import move_symbols

    src_pkg = _make_pkg(tmp_path, "src_pkg")
    dst_pkg = _make_pkg(tmp_path, "dst_pkg")
    src = src_pkg / "source.py"
    tgt = dst_pkg / "target.py"
    src.write_text("from ... import x\n\n\ndef Moved():\n    return x\n")
    tgt.write_text("")

    plan = move_symbols(src, tgt, ["Moved"], workspace_root=tmp_path)

    assert any("relative import" in w.lower() for w in plan.warnings), plan.warnings
    target_after = tgt.read_text()
    assert "from ... import x" not in target_after


def test_relative_import_cross_package_real_files(tmp_path: Path) -> None:
    """AC2: a real on-disk cross-package move writes an absolute import into the
    target file (two-package tmp workspace)."""
    from axm_anvil.core.move import move_symbols

    src_pkg = _make_pkg(tmp_path, "alpha")
    (src_pkg / "utils.py").write_text("def helper():\n    return 7\n")
    dst_pkg = _make_pkg(tmp_path, "beta")
    src = src_pkg / "source.py"
    tgt = dst_pkg / "target.py"
    src.write_text("from .utils import helper\n\n\ndef Moved():\n    return helper()\n")
    tgt.write_text("")

    move_symbols(src, tgt, ["Moved"], workspace_root=tmp_path)

    target_after = tgt.read_text()
    assert "from alpha.utils import helper" in target_after


def test_fixture_out_of_scope_warns(tmp_path: Path) -> None:
    """AC3, AC5: moving a test out of the directory subtree covered by the
    conftest providing its fixture emits a structured out-of-scope warning;
    the move itself still succeeds (detection-only)."""
    from axm_anvil.core.move import move_symbols

    dir_a = tmp_path / "dir_a"
    dir_b = tmp_path / "dir_b"
    dir_a.mkdir()
    dir_b.mkdir()
    (dir_a / "conftest.py").write_text(
        "import pytest\n\n\n@pytest.fixture\ndef my_fixture():\n    return 1\n"
    )
    from_file = dir_a / "test_thing.py"
    to_file = dir_b / "test_thing.py"
    from_file.write_text(
        "def test_uses_fixture(my_fixture):\n    assert my_fixture == 1\n"
    )
    to_file.write_text("")

    plan = move_symbols(
        from_file, to_file, ["test_uses_fixture"], workspace_root=tmp_path
    )

    assert any("my_fixture" in w and "scope" in w.lower() for w in plan.warnings), (
        plan.warnings
    )


def test_fixture_same_scope_no_warn(tmp_path: Path) -> None:
    """AC4, AC5: when the conftest sits at a common ancestor of both source and
    target, the moved test's fixture stays in scope and no scope warning is
    emitted."""
    from axm_anvil.core.move import move_symbols

    root = tmp_path / "root"
    sub_a = root / "a"
    sub_b = root / "b"
    sub_a.mkdir(parents=True)
    sub_b.mkdir(parents=True)
    (root / "conftest.py").write_text(
        "import pytest\n\n\n@pytest.fixture\ndef my_fixture():\n    return 1\n"
    )
    from_file = sub_a / "test_thing.py"
    to_file = sub_b / "test_thing.py"
    from_file.write_text(
        "def test_uses_fixture(my_fixture):\n    assert my_fixture == 1\n"
    )
    to_file.write_text("")

    plan = move_symbols(
        from_file, to_file, ["test_uses_fixture"], workspace_root=tmp_path
    )

    assert not any("my_fixture" in w and "scope" in w.lower() for w in plan.warnings), (
        plan.warnings
    )


def test_cross_package_move_no_cycle_succeeds(tmp_path: Path) -> None:
    """AC3, AC6: an acyclic cross-package move succeeds, no skip warning."""
    _write_workspace(tmp_path)
    pkg_a = tmp_path / "packages" / "pkg_a" / "src" / "pkg_a"
    pkg_b = tmp_path / "packages" / "pkg_b" / "src" / "pkg_b"
    x = pkg_a / "x.py"
    y = pkg_b / "y.py"
    x.write_text("def Bar():\n    return 1\n\ndef Foo():\n    return 42\n")
    y.write_text("def existing():\n    return 0\n")

    plan = move_symbols(x, y, ["Foo"], workspace_root=tmp_path)

    assert "Foo" in plan.moved_names
    assert "def Foo" in y.read_text()
    assert "def Foo" not in x.read_text()
    assert not any("cycle detection skipped" in w for w in plan.warnings), plan.warnings


@pytest.mark.integration
def test_include_helpers_false_real_files(tmp_path: Path) -> None:
    """AC2: written target file does not define the skipped helper."""
    src = tmp_path / "src_mod.py"
    tgt = tmp_path / "tgt_mod.py"
    src.write_text(_SOURCE)
    tgt.write_text(_TARGET)
    move_symbols(
        src,
        tgt,
        ["public_fn"],
        workspace_root=tmp_path,
        include_helpers=False,
    )
    written = tgt.read_text()
    assert "def _helper" not in written
    assert "def public_fn" in written


def test_insert_after_none_appends_at_end(tmp_path: Path) -> None:
    """AC2: insert_after=None preserves the historical end-append contract."""
    src = tmp_path / "source.py"
    tgt = tmp_path / "target.py"
    src.write_text("def Moved():\n    return 1\n")
    tgt.write_text("def Anchor():\n    return 0\n\n\ndef Tail():\n    return 2\n")

    plan = move_symbols(src, tgt, ["Moved"], dry_run=True, insert_after=None)

    text = plan.target_text_new
    assert text.index("def Moved") > text.index("def Anchor")
    assert text.index("def Moved") > text.index("def Tail")


def test_insert_after_absent_warns_and_appends(tmp_path: Path) -> None:
    """AC3: an absent insert_after anchor appends at end and adds a warning."""
    src = tmp_path / "source.py"
    tgt = tmp_path / "target.py"
    src.write_text("def Moved():\n    return 1\n")
    tgt.write_text("def Anchor():\n    return 0\n")

    plan = move_symbols(src, tgt, ["Moved"], dry_run=True, insert_after="NoSuch")

    text = plan.target_text_new
    assert text.index("def Moved") > text.index("def Anchor")
    assert any("NoSuch" in w for w in plan.warnings)


def test_move_warnings_surface_post_ruff_failure(
    tmp_path: Path, mocker: MockerFixture
) -> None:
    """AC1, AC3: a real move carries no re-validation warning, but if the
    post-write ruff pass leaves a written file unparseable, the move still
    succeeds and the plan carries a re-validation warning naming the file."""
    src = tmp_path / "source.py"
    tgt = tmp_path / "target.py"
    src.write_text("def kept():\n    return 1\n\n\ndef Moved():\n    return 2\n")
    tgt.write_text("def Anchor():\n    return 0\n")

    # Normal real move: no re-validation warning.
    plan_ok = move_symbols(src, tgt, ["Moved"], workspace_root=tmp_path)
    assert "def Moved" in tgt.read_text()
    assert not any("re-validation" in w for w in plan_ok.warnings), plan_ok.warnings

    # Force a destructive post-write ruff pass that mangles a written file.
    src2 = tmp_path / "source2.py"
    tgt2 = tmp_path / "target2.py"
    src2.write_text("def kept2():\n    return 1\n\n\ndef Moved2():\n    return 2\n")
    tgt2.write_text("def Anchor2():\n    return 0\n")

    def _corrupt(action_args: list[str], warnings: list[str]) -> None:
        if str(tgt2) in action_args:
            tgt2.write_text("def broken(:\n    return\n")

    mocker.patch("axm_anvil.core.postprocess._run_ruff", side_effect=_corrupt)

    plan_bad = move_symbols(src2, tgt2, ["Moved2"], workspace_root=tmp_path)

    revalidation = [w for w in plan_bad.warnings if "re-validation" in w]
    assert revalidation, plan_bad.warnings
    assert any(str(tgt2) in w for w in revalidation), revalidation


def test_move_cross_folder_no_relative_to_error(tmp_path: Path) -> None:
    """AC1: a cross-folder move (source and target under different subdirs of
    the same root) completes without raising a ``relative_to`` ValueError.

    The source subtree carries its own ``pyproject.toml`` so
    ``_find_workspace_root(source)`` resolves to ``root/a`` (not the common
    ``root``). The target lives under ``root/b``, which is *not* under
    ``root/a``, forcing the ``relative_to`` fallback. The fix computes a
    common base (``commonpath``) that contains both paths, so the move
    succeeds instead of raising a second cryptic ValueError.
    """
    (tmp_path / "pyproject.toml").write_text("[project]\nname='root'\n")
    sub_a = tmp_path / "a"
    sub_b = tmp_path / "b"
    sub_a.mkdir()
    sub_b.mkdir()
    (sub_a / "pyproject.toml").write_text("[project]\nname='a'\n")
    source = sub_a / "x.py"
    target = sub_b / "x.py"
    source.write_text("def moved():\n    return 1\n\n\ndef stays():\n    return 2\n")
    target.write_text("")

    plan = move_symbols(source, target, ["moved"])

    assert "moved" in plan.moved_names
    assert "def moved" in target.read_text()
    assert "def moved" not in source.read_text()
    assert "def stays" in source.read_text()


def test_move_cross_package_clear_error_or_success(tmp_path: Path) -> None:
    """AC2: a cross-package move (source and target in disjoint package trees
    with no common parent below the resolved root) completes, or fails with a
    clear typed :class:`MovePathError` — never a raw cryptic ``relative_to``
    traceback.

    ``pkg_a`` and ``pkg_b`` are independent roots (each with its own
    ``pyproject.toml``) under a shared ``tmp_path``; passing no
    ``workspace_root`` makes ``_find_workspace_root(source)`` resolve to
    ``pkg_a``, which does not contain the target. ``commonpath`` still finds
    ``tmp_path`` as a valid common base, so the move succeeds with both
    relative paths anchored there.
    """
    pkg_a = tmp_path / "pkg_a"
    pkg_b = tmp_path / "pkg_b"
    pkg_a.mkdir()
    pkg_b.mkdir()
    (pkg_a / "pyproject.toml").write_text("[project]\nname='pkg_a'\n")
    (pkg_b / "pyproject.toml").write_text("[project]\nname='pkg_b'\n")
    source = pkg_a / "x.py"
    target = pkg_b / "y.py"
    source.write_text("def moved():\n    return 1\n\n\ndef stays():\n    return 2\n")
    target.write_text("")

    try:
        plan = move_symbols(source, target, ["moved"])
    except MovePathError:
        # Acceptable: a typed move error (mapped to ToolResult) rather than a
        # bare ValueError. The contract is "clear typed error, not cryptic".
        return
    except ValueError as exc:  # pragma: no cover - guards against regression
        pytest.fail(f"raw ValueError leaked instead of typed MovePathError: {exc}")

    assert "moved" in plan.moved_names
    assert "def moved" in target.read_text()
    assert "def moved" not in source.read_text()


def test_move_same_folder_unchanged(tmp_path: Path) -> None:
    """AC3: same-folder moves continue to work unchanged (no regression).

    Source and target share a directory, so the primary ``relative_to`` branch
    succeeds and the fallback is never exercised.
    """
    (tmp_path / "pyproject.toml").write_text("[project]\nname='root'\n")
    source = tmp_path / "source.py"
    target = tmp_path / "target.py"
    source.write_text("def moved():\n    return 1\n\n\ndef stays():\n    return 2\n")
    target.write_text("")

    plan = move_symbols(source, target, ["moved"])

    assert "moved" in plan.moved_names
    assert "def moved" in target.read_text()
    assert "def moved" not in source.read_text()
    assert "def stays" in source.read_text()
