from __future__ import annotations

from pathlib import Path

import pytest

from axm_anvil.core.move import move_symbols

pytestmark = pytest.mark.integration

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
