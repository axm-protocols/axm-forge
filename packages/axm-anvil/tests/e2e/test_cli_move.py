from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e


SOURCE_CODE = '''\
from __future__ import annotations


class TestFilesystemInvalidation:
    """Fixture class for CLI move e2e tests."""

    def run(self) -> int:
        return 1


class Untouched:
    pass
'''

TARGET_CODE = """\
from __future__ import annotations
"""


@pytest.fixture
def fixture_dir(tmp_path: Path) -> Path:
    src = tmp_path / "source.py"
    tgt = tmp_path / "target.py"
    src.write_text(SOURCE_CODE)
    tgt.write_text(TARGET_CODE)
    return tmp_path


def _run_cli(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["uv", "run", "axm-anvil", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )


def test_cli_move_dry_run(fixture_dir: Path) -> None:
    src = fixture_dir / "source.py"
    tgt = fixture_dir / "target.py"
    before_src = src.read_text()
    before_tgt = tgt.read_text()

    result = _run_cli(
        fixture_dir,
        "move",
        str(src),
        str(tgt),
        "TestFilesystemInvalidation",
        "--dry-run",
    )

    assert result.returncode == 0, result.stderr
    assert "ast_move" in result.stdout
    assert "TestFilesystemInvalidation" in result.stdout
    assert src.read_text() == before_src
    assert tgt.read_text() == before_tgt


def test_cli_move_success(fixture_dir: Path) -> None:
    src = fixture_dir / "source.py"
    tgt = fixture_dir / "target.py"

    result = _run_cli(
        fixture_dir,
        "move",
        str(src),
        str(tgt),
        "TestFilesystemInvalidation",
    )

    assert result.returncode == 0, result.stderr
    assert "TestFilesystemInvalidation" in tgt.read_text()


def test_cli_symbol_not_found(fixture_dir: Path) -> None:
    src = fixture_dir / "source.py"
    tgt = fixture_dir / "target.py"

    result = _run_cli(
        fixture_dir,
        "move",
        str(src),
        str(tgt),
        "Nope",
    )

    assert result.returncode == 1
    assert "not found" in result.stderr.lower()
    assert result.stdout.strip() == ""


def test_cli_help_lists_move(fixture_dir: Path) -> None:
    result = _run_cli(fixture_dir, "--help")

    assert result.returncode == 0, result.stderr
    assert "move" in result.stdout
