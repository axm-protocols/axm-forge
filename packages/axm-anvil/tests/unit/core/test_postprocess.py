from __future__ import annotations

from pathlib import Path

from pytest_mock import MockerFixture

from axm_anvil.core.postprocess import _ruff_fix


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
