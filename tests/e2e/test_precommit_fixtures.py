"""E2E: prek must leave excluded snapshot fixtures byte-intact.

Regression guard for AC2 of the pre-commit fixtures-exclude ticket: the
workspace-root ``trailing-whitespace`` and ``end-of-file-fixer`` hooks carry
``exclude: tests/fixtures/(snapshots|goldens)/``. A file written under such a
path with trailing whitespace (and no final newline) would normally be rewritten
by both mutating hooks; the exclude must protect it.

The test reuses the *real* exclude patterns declared in the workspace-root
``.pre-commit-config.yaml`` inside an isolated throwaway git repo, then runs
``prek`` over the fixture and byte-compares before/after.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.e2e

# tests/e2e/ -> tests/ -> axm-forge/
_ROOT = Path(__file__).resolve().parents[2]
_CONFIG = _ROOT / ".pre-commit-config.yaml"
_MUTATING_HOOKS = ("trailing-whitespace", "end-of-file-fixer")


def _pre_commit_hooks_repo() -> dict:
    """Return the pre-commit-hooks repo entry, keeping only the mutating hooks."""
    data = yaml.safe_load(_CONFIG.read_text())
    for repo in data["repos"]:
        ids = {hook["id"] for hook in repo.get("hooks", [])}
        if set(_MUTATING_HOOKS).issubset(ids):
            kept = [h for h in repo["hooks"] if h["id"] in _MUTATING_HOOKS]
            return {"repo": repo["repo"], "rev": repo["rev"], "hooks": kept}
    raise AssertionError("mutating hooks repo not found in root config")


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.mark.skipif(shutil.which("prek") is None, reason="prek not installed")
def test_prek_leaves_snapshot_fixture_byte_intact(tmp_path: Path) -> None:
    repo = _pre_commit_hooks_repo()

    # Sanity: the real config actually excludes the fixtures paths on both hooks.
    for hook in repo["hooks"]:
        assert "tests/fixtures/(snapshots|goldens)/" in (hook.get("exclude") or "")

    (tmp_path / ".pre-commit-config.yaml").write_text(
        yaml.safe_dump({"repos": [repo]}, sort_keys=False)
    )

    fixture = tmp_path / "tests" / "fixtures" / "snapshots" / "snap.yaml"
    fixture.parent.mkdir(parents=True)
    # Trailing space AND no final newline -> would trip BOTH mutating hooks.
    original = b"key: value \nother: x"
    fixture.write_bytes(original)

    _git("init", cwd=tmp_path)
    _git("config", "user.email", "test@example.com", cwd=tmp_path)
    _git("config", "user.name", "test", cwd=tmp_path)
    _git("add", "-A", cwd=tmp_path)

    result = subprocess.run(
        ["prek", "run", "--all-files"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    # The fixture must survive untouched: exclude short-circuits the hooks.
    assert fixture.read_bytes() == original
    # And prek must not report our excluded path among any autofixed files.
    assert "snap.yaml" not in result.stdout
