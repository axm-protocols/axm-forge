from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from pytest_mock import MockerFixture

from axm_anvil.core.postprocess import _ruff_fix


def _ok_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")


def test_ruff_invoked_via_python_m(tmp_path: Path, mocker: MockerFixture) -> None:
    """AC1: ruff is invoked via ``sys.executable -m ruff``, not bare ``ruff``."""
    captured: list[list[str]] = []

    def fake_run(
        argv: list[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        captured.append(argv)
        return _ok_run()

    mocker.patch("axm_anvil.core.postprocess.subprocess.run", side_effect=fake_run)
    mocker.patch("axm_anvil.core.postprocess._revalidate", return_value=None)

    source = tmp_path / "a.py"
    target = tmp_path / "b.py"
    _ruff_fix(source, target)

    assert captured, "ruff was never invoked"
    for argv in captured:
        assert argv[:3] == [sys.executable, "-m", "ruff"], argv


def test_ruff_missing_emits_skipped_warning(
    tmp_path: Path, mocker: MockerFixture
) -> None:
    """AC2: missing ruff yields an explicit 'skipped' warning, no raise."""

    def fake_run(
        _argv: list[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=[],
            returncode=1,
            stdout="",
            stderr="/usr/bin/python: No module named ruff",
        )

    mocker.patch("axm_anvil.core.postprocess.subprocess.run", side_effect=fake_run)
    mocker.patch("axm_anvil.core.postprocess._revalidate", return_value=None)

    source = tmp_path / "a.py"
    target = tmp_path / "b.py"
    warnings = _ruff_fix(source, target)

    assert warnings, "expected a skipped-cleanup warning"
    joined = " ".join(warnings).lower()
    assert "unavailable" in joined or "skipped" in joined, warnings


def test_ruff_fix_warns_when_post_ruff_file_unparseable(
    tmp_path: Path, mocker: MockerFixture
) -> None:
    """AC1, AC3: a destructive post-write ruff pass that leaves a file unparseable
    is surfaced through the returned warnings list, with the file named."""
    source = tmp_path / "source.py"
    target = tmp_path / "target.py"
    source.write_text("def kept():\n    return 1\n")
    target.write_text("def moved():\n    return 2\n")

    def _corrupt_source(action_args: list[str], warnings: list[str]) -> None:
        # Simulate a destructive `ruff --fix` mangling the source into invalid syntax.
        if str(source) in action_args:
            source.write_text("def broken(:\n    return\n")

    mocker.patch("axm_anvil.core.postprocess._run_ruff", side_effect=_corrupt_source)

    warnings = _ruff_fix(source, target)

    revalidation = [w for w in warnings if "re-validation" in w]
    assert revalidation, warnings
    assert any(str(source) in w for w in revalidation), revalidation


def test_ruff_fix_no_warning_when_files_parse(
    tmp_path: Path, mocker: MockerFixture
) -> None:
    """AC2: when the post-write ruff pass leaves files valid, no re-validation
    warning is added (re-validation is additive, not a behavior change)."""
    source = tmp_path / "source.py"
    target = tmp_path / "target.py"
    source.write_text("def kept():\n    return 1\n")
    target.write_text("def moved():\n    return 2\n")

    mocker.patch("axm_anvil.core.postprocess._run_ruff", return_value=None)

    warnings = _ruff_fix(source, target)

    assert not any("re-validation" in w for w in warnings), warnings
