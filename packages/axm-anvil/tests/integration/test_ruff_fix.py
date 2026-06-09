from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from axm_anvil.core import postprocess
from axm_anvil.core.move import move_symbols

pytestmark = pytest.mark.integration

_SOURCE = "def kept():\n    return 1\n\n\ndef moved():\n    return 2\n"
_TARGET = ""


def _seed(tmp_path: Path) -> tuple[Path, Path]:
    """Lay out a minimal movable source/target pair under ``tmp_path``."""
    source = tmp_path / "source.py"
    target = tmp_path / "target.py"
    source.write_text(_SOURCE)
    target.write_text(_TARGET)
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'tmp_pkg'\nversion = '0.1.0'\n"
    )
    return source, target


def test_move_symbols__post_ruff_unparseable_source_surfaced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC1, AC3: a destructive post-write ruff pass that leaves a moved file
    unparseable is surfaced through ``MovePlan.warnings`` with the file named.

    Exercised through the public ``move_symbols`` pipeline: the post-write ruff
    pass is the real boundary, so corrupting it via the ``_run_ruff`` seam mimics
    a destructive ``ruff --fix`` mangling the source into invalid syntax.
    """
    source, target = _seed(tmp_path)

    def _corrupt_source(action_args: list[str], warnings: list[str]) -> None:
        if str(source) in action_args:
            source.write_text("def broken(:\n    return\n")

    monkeypatch.setattr(postprocess, "_run_ruff", _corrupt_source)

    plan = move_symbols(source, target, ["moved"], dry_run=False)

    revalidation = [w for w in plan.warnings if "re-validation" in w]
    assert revalidation, plan.warnings
    assert any(str(source) in w for w in revalidation), revalidation


def test_move_symbols__post_ruff_parseable_no_revalidation_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC2: when the post-write ruff pass leaves files valid, no re-validation
    warning is added (re-validation is additive, not a behavior change).

    Exercised through the public ``move_symbols`` pipeline with the ruff pass
    no-op'd so the written files stay valid.
    """
    source, target = _seed(tmp_path)

    def _noop(action_args: list[str], warnings: list[str]) -> None:
        return None

    monkeypatch.setattr(postprocess, "_run_ruff", _noop)

    plan = move_symbols(source, target, ["moved"], dry_run=False)

    assert not any("re-validation" in w for w in plan.warnings), plan.warnings


def test_move_symbols__post_ruff_invoked_via_python_m(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC1: the post-write ruff pass invokes ruff via ``sys.executable -m ruff``,
    not a bare ``ruff`` PATH binary.

    Exercised through the public ``move_symbols`` pipeline by capturing the real
    subprocess argv at the ``postprocess.subprocess.run`` seam.
    """
    source, target = _seed(tmp_path)
    captured: list[list[str]] = []

    def _capture_run(
        argv: list[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        captured.append(argv)
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

    monkeypatch.setattr(postprocess.subprocess, "run", _capture_run)

    move_symbols(source, target, ["moved"], dry_run=False)

    assert captured, "ruff was never invoked"
    for argv in captured:
        assert argv[:3] == [sys.executable, "-m", "ruff"], argv


def test_move_symbols__post_ruff_missing_emits_skipped_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC2: a missing ruff module yields an explicit 'skipped/unavailable'
    warning on the plan, never a raise.

    Exercised through the public ``move_symbols`` pipeline by faking the
    'No module named ruff' subprocess result at the ``postprocess`` seam.
    """
    source, target = _seed(tmp_path)

    def _no_ruff(
        _argv: list[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=[],
            returncode=1,
            stdout="",
            stderr="/usr/bin/python: No module named ruff",
        )

    monkeypatch.setattr(postprocess.subprocess, "run", _no_ruff)

    plan = move_symbols(source, target, ["moved"], dry_run=False)

    joined = " ".join(plan.warnings).lower()
    assert "unavailable" in joined or "skipped" in joined, plan.warnings
