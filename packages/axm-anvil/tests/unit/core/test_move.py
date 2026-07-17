from __future__ import annotations

from pathlib import Path

import libcst as cst

from axm_anvil._cst.blocks import Block, extract_blocks
from axm_anvil.core.move import (
    PYTEST_BUILTIN_FIXTURES,
    _process_callers,
    detect_fixture_dependencies,
)


def _blocks_for(source: str, names: list[str]) -> list[Block]:
    """Parse ``source`` in memory and extract the requested top-level blocks."""
    return extract_blocks(cst.parse_module(source), names)


def test_builtin_fixture_never_warns() -> None:
    """AC1: a moved test using only the builtin ``tmp_path`` fixture is not
    flagged as a non-builtin fixture dependency (in-memory detection)."""
    assert "tmp_path" in PYTEST_BUILTIN_FIXTURES
    blocks = _blocks_for("def test_x(tmp_path):\n    return tmp_path\n", ["test_x"])

    used = detect_fixture_dependencies(blocks, local_names=set())

    assert "tmp_path" not in used
    assert used == set()


def test_fixture_usage_detected() -> None:
    """AC2: a moved ``def test_x(my_fixture)`` whose parameter is neither a
    builtin nor a locally-resolvable name is identified as a fixture
    dependency (in-memory detection, no filesystem I/O)."""
    blocks = _blocks_for("def test_x(my_fixture):\n    return my_fixture\n", ["test_x"])

    used = detect_fixture_dependencies(blocks, local_names=set())

    assert "my_fixture" in used


def test_fixture_param_resolvable_as_local_excluded() -> None:
    """AC2: a test parameter whose name is also a local/imported symbol is not
    treated as a fixture dependency."""
    blocks = _blocks_for("def test_x(helper):\n    return helper\n", ["test_x"])

    used = detect_fixture_dependencies(blocks, local_names={"helper"})

    assert "helper" not in used


def test_fixture_self_and_defaults_excluded() -> None:
    """AC2: ``self`` and parameters carrying a default are never fixtures."""
    blocks = _blocks_for(
        "class C:\n    def test_m(self, real_fixture, opt=1):\n"
        "        return real_fixture\n",
        ["C"],
    )

    used = detect_fixture_dependencies(blocks, local_names=set())

    assert "self" not in used
    assert "opt" not in used


def test_out_of_workspace_file_yields_caller_warning(tmp_path: Path) -> None:
    """AC1: a source file outside ``workspace_root`` (unresolvable import path)
    makes ``_process_callers`` return a non-empty warnings channel instead of
    silently swallowing the ``ValueError``."""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    outside = tmp_path / "elsewhere" / "stray.py"

    _texts, _rewrites, warnings = _process_callers(
        workspace, ["foo"], outside, workspace / "target.py"
    )

    assert warnings


def test_caller_warning_names_unresolved_file(tmp_path: Path) -> None:
    """AC2: the emitted warning names the offending file so the user can act
    on it."""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    outside = tmp_path / "elsewhere" / "stray.py"

    _texts, _rewrites, warnings = _process_callers(
        workspace, ["foo"], outside, workspace / "target.py"
    )

    assert str(outside) in warnings[0]


def test_in_root_move_emits_no_caller_warning(tmp_path: Path) -> None:
    """AC3: a move whose source/target both resolve under ``workspace_root``
    produces no caller-skipped warning (no spurious noise)."""
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    source = pkg / "a.py"
    source.write_text("def foo():\n    return 1\n")
    target = pkg / "b.py"
    target.write_text("")

    _texts, _rewrites, warnings = _process_callers(tmp_path, ["foo"], source, target)

    assert warnings == []


def _make_caller_workspace(tmp_path: Path) -> tuple[Path, Path]:
    """Scaffold a package with a from-import and a module-import caller.

    Returns ``(source, target)`` for :func:`_process_callers`.
    """
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    source = pkg / "a.py"
    source.write_text("def foo():\n    return 1\n")
    target = pkg / "b.py"
    target.write_text("")
    (pkg / "from_caller.py").write_text(
        "from pkg.a import foo\n\n\ndef use():\n    return foo()\n"
    )
    (pkg / "mod_caller.py").write_text(
        "import pkg.a\n\n\ndef use():\n    return pkg.a.foo()\n"
    )
    return source, target


def test_process_callers_reads_each_file_at_most_once(tmp_path: Path, mocker) -> None:
    """AC1: a single move scans the workspace once -- every ``.py`` file is read
    at most once across the whole caller-discovery pass."""
    source, target = _make_caller_workspace(tmp_path)
    spy = mocker.spy(Path, "read_text")

    _process_callers(tmp_path, ["foo"], source, target)

    read_counts: dict[Path, int] = {}
    for call in spy.call_args_list:
        resolved = call.args[0].resolve()
        read_counts[resolved] = read_counts.get(resolved, 0) + 1
    for py_file in tmp_path.rglob("*.py"):
        assert read_counts.get(py_file.resolve(), 0) <= 1


def test_process_callers_scans_once_and_shares_collection(
    tmp_path: Path, mocker
) -> None:
    """AC3: the orchestrator builds the scan once and threads the *same*
    collection into both discovery passes."""
    import axm_anvil.core.move as move_mod

    source, target = _make_caller_workspace(tmp_path)
    scan_spy = mocker.spy(move_mod, "_scan_workspace_py_files")
    from_spy = mocker.spy(move_mod, "_discover_callers")
    mod_spy = mocker.spy(move_mod, "_discover_module_import_callers")

    _process_callers(tmp_path, ["foo"], source, target)

    assert scan_spy.call_count == 1
    scanned = scan_spy.spy_return
    assert from_spy.call_args.args[0] is scanned
    assert mod_spy.call_args.args[0] is scanned
