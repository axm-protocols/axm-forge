from __future__ import annotations

from pathlib import Path

import pytest

from axm_anvil.core.move import move_symbols

pytestmark = pytest.mark.integration


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
