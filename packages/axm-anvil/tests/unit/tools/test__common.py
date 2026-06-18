"""Unit tests for :mod:`axm_anvil.tools._common` (pure helpers, no real I/O).

``normalize_execute_args`` and ``exception_to_result`` are the plumbing shared
by ``anvil_move`` and ``anvil_extract``. Both are pure functions, so the
assertions target their return values directly without touching the filesystem.
"""

from __future__ import annotations

from pathlib import Path

from axm_anvil.core.plan import (
    ImportCycleError,
    SharedHelpersError,
    SymbolAlreadyExistsError,
    SymbolNotFoundError,
)
from axm_anvil.tools._common import exception_to_result, normalize_execute_args


def test_normalize_parses_csv_and_drops_empty_entries() -> None:
    """CSV symbols are split, stripped, and empty fragments are dropped."""
    _root, _src, _tgt, symbols = normalize_execute_args(
        ".", " Foo , ,Bar ,", "a.py", "b.py"
    )
    assert symbols == ["Foo", "Bar"]


def test_normalize_resolves_relative_paths_against_root() -> None:
    """Relative from/to files are anchored under the resolved workspace root."""
    root, src, tgt, _symbols = normalize_execute_args(
        ".", "Foo", "pkg/a.py", "pkg/b.py"
    )
    assert root == Path(".").resolve()
    assert src == root / "pkg/a.py"
    assert tgt == root / "pkg/b.py"


def test_normalize_keeps_absolute_paths_unchanged() -> None:
    """An absolute from/to file is preserved verbatim, not re-anchored."""
    abs_src = str(Path("/tmp/x/src.py"))
    _root, src, _tgt, _symbols = normalize_execute_args(".", "Foo", abs_src, "rel.py")
    assert src == Path(abs_src)


def test_exception_symbol_not_found_maps_to_source_module_message() -> None:
    """SymbolNotFoundError surfaces the 'not found in source module' message."""
    result = exception_to_result(SymbolNotFoundError("Foo"))
    assert result.success is False
    assert result.error == "Symbol Foo not found in source module"


def test_exception_already_exists_maps_to_target_module_message() -> None:
    """SymbolAlreadyExistsError surfaces the 'already exists in target' message."""
    result = exception_to_result(SymbolAlreadyExistsError("Foo"))
    assert result.success is False
    assert result.error == "Symbol Foo already exists in target module"


def test_exception_shared_helpers_lists_the_helpers() -> None:
    """SharedHelpersError joins the offending helper names into the error."""
    result = exception_to_result(SharedHelpersError(["a", "b"]))
    assert result.success is False
    assert result.error == "Shared helpers detected: a, b"


def test_exception_import_cycle_passes_through_its_str() -> None:
    """ImportCycleError is surfaced via its own rendered cycle string."""
    exc = ImportCycleError(["m1", "m2"])
    result = exception_to_result(exc)
    assert result.success is False
    assert result.error == str(exc)


def test_exception_not_implemented_explains_extract_phase() -> None:
    """A bare NotImplementedError is mapped to the extract-policy message."""
    result = exception_to_result(NotImplementedError())
    assert result.success is False
    assert "not yet implemented" in (result.error or "")


def test_exception_unknown_falls_back_to_str() -> None:
    """An unmodelled exception falls through to its string form."""
    result = exception_to_result(ValueError("boom"))
    assert result.success is False
    assert result.error == "boom"
