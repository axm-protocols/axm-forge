"""Integration tests for the on-disk rewrite target checks.

Real filesystem (``tmp_path``), strictly read-only: pins the blocking
diagnostics ``check_rewrite_targets`` must emit for an absent, non-regular or
stale rewrite target, and their propagation through ``run_fs_checks``.

The new symbol is resolved at call time rather than imported at module level,
so a missing implementation fails the assertion of the test that needs it
instead of breaking collection for the whole module.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import cast

import pytest

from axm_edit.core import precheck_fs
from axm_edit.core.precheck_fs import run_fs_checks
from axm_edit.models.check import CheckDiagnostic

pytestmark = pytest.mark.integration

_EMPTY_DIGEST = hashlib.sha256(b"").hexdigest()

_RewriteTargetCheck = Callable[
    [Path, Sequence[dict[str, object]]],
    list[CheckDiagnostic],
]


def _rewrite_target_check() -> _RewriteTargetCheck:
    """Resolve the on-disk rewrite target check this ticket must expose."""
    check = getattr(precheck_fs, "check_rewrite_targets", None)
    assert callable(check), (
        "axm_edit.core.precheck_fs must expose check_rewrite_targets(root, ops)"
    )
    return cast("_RewriteTargetCheck", check)


def _digest(path: Path) -> str:
    """Return the sha256 hex digest of the bytes of *path*."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rewrite(
    file: str,
    checksum: str,
    content: str = "value = 2\n",
) -> dict[str, object]:
    """Build a raw rewrite payload targeting *file*."""
    return {
        "op": "rewrite",
        "file": file,
        "content": content,
        "checksum": checksum,
    }


def _codes(diagnostics: Sequence[CheckDiagnostic]) -> list[str]:
    """Return the upper-cased codes of *diagnostics*, in order."""
    return [diagnostic.code.upper() for diagnostic in diagnostics]


def test_matching_regular_target_yields_no_diagnostic(tmp_path: Path) -> None:
    """AC1: an existing regular file whose digest matches is clean."""
    target = tmp_path / "mod.py"
    target.write_text("value = 1\n", encoding="utf-8")

    diagnostics = _rewrite_target_check()(
        tmp_path,
        [_rewrite("mod.py", _digest(target))],
    )

    assert diagnostics == []


def test_absent_target_reports_rewrite_target_missing(tmp_path: Path) -> None:
    """AC1: a rewrite on a file that does not exist is blocking."""
    diagnostics = _rewrite_target_check()(
        tmp_path,
        [_rewrite("ghost.py", _EMPTY_DIGEST)],
    )

    assert _codes(diagnostics) == ["REWRITE_TARGET_MISSING"]
    assert diagnostics[0].severity == "error"
    assert diagnostics[0].op_index == 0
    assert diagnostics[0].file == "ghost.py"


def test_symlink_target_reports_rewrite_target_not_regular(
    tmp_path: Path,
) -> None:
    """AC1: a symlinked target is refused as non-regular."""
    real = tmp_path / "real.py"
    real.write_text("value = 1\n", encoding="utf-8")
    link = tmp_path / "link.py"
    link.symlink_to(real)

    diagnostics = _rewrite_target_check()(
        tmp_path,
        [_rewrite("link.py", _digest(real))],
    )

    assert _codes(diagnostics) == ["REWRITE_TARGET_NOT_REGULAR"]
    assert diagnostics[0].severity == "error"


def test_directory_target_reports_rewrite_target_not_regular(
    tmp_path: Path,
) -> None:
    """AC1: a directory bearing the target name is refused as non-regular."""
    (tmp_path / "pkg.py").mkdir()

    diagnostics = _rewrite_target_check()(
        tmp_path,
        [_rewrite("pkg.py", _EMPTY_DIGEST)],
    )

    assert _codes(diagnostics) == ["REWRITE_TARGET_NOT_REGULAR"]
    assert diagnostics[0].severity == "error"


def test_stale_digest_reports_rewrite_checksum_stale(tmp_path: Path) -> None:
    """AC1: a file mutated after the digest was taken is blocking."""
    target = tmp_path / "mod.py"
    target.write_text("value = 1\n", encoding="utf-8")
    stale = _digest(target)
    target.write_text("value = 99\n", encoding="utf-8")

    diagnostics = _rewrite_target_check()(tmp_path, [_rewrite("mod.py", stale)])

    assert _codes(diagnostics) == ["REWRITE_CHECKSUM_STALE"]
    assert diagnostics[0].severity == "error"
    assert diagnostics[0].file == "mod.py"


def test_run_fs_checks_surfaces_the_rewrite_diagnostics(
    tmp_path: Path,
) -> None:
    """AC2: a batch holding a stale rewrite reports it through run_fs_checks."""
    target = tmp_path / "mod.py"
    target.write_text("value = 1\n", encoding="utf-8")
    stale = _digest(target)
    target.write_text("value = 99\n", encoding="utf-8")

    diagnostics = run_fs_checks(tmp_path, [_rewrite("mod.py", stale)])

    assert "REWRITE_CHECKSUM_STALE" in _codes(diagnostics)
    assert target.read_text(encoding="utf-8") == "value = 99\n"
