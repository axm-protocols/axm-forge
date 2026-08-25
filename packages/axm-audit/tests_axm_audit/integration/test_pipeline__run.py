"""Integration tests for the atomic apply + import-backfill contract of
``axm_audit.core.fix.pipeline.run`` (AXM-1768).

Real filesystem + git + libcst. Each test seeds a minimal package, git-
initialises it (required for ``apply=True``), and exercises the public
``run(...)`` entry point end-to-end.
"""

from __future__ import annotations

import hashlib
import subprocess
import tempfile
from pathlib import Path

import pytest

from axm_audit.core.fix import pipeline
from axm_audit.core.fix.pipeline import run

pytestmark = pytest.mark.integration


_PYPROJECT = '[project]\nname = "pkg"\nversion = "0.0.0"\nrequires-python = ">=3.12"\n'


def _tree_hash(root: Path) -> str:
    """Stable hash of every file's relative path + bytes under *root*."""
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        if p.is_file():
            h.update(str(p.relative_to(root)).encode())
            h.update(b"\0")
            h.update(p.read_bytes())
            h.update(b"\0")
    return h.hexdigest()


def _git_init(pkg: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=pkg, check=True, capture_output=True)  # noqa: S607
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=pkg, check=True)  # noqa: S607
    subprocess.run(["git", "config", "user.name", "t"], cwd=pkg, check=True)  # noqa: S607
    subprocess.run(["git", "add", "-A"], cwd=pkg, check=True, capture_output=True)  # noqa: S607
    subprocess.run(
        ["git", "commit", "-q", "-m", "init"],  # noqa: S607
        cwd=pkg,
        check=True,
        capture_output=True,
    )


def _make_corpus(project: Path) -> None:
    """Minimal AXM-shaped package with a tests/ tree the pipeline can act on."""
    (project / "pyproject.toml").write_text(_PYPROJECT)
    (project / "src" / "pkg").mkdir(parents=True)
    (project / "src" / "pkg" / "__init__.py").write_text("")
    (project / "src" / "pkg" / "thing.py").write_text(
        "def add(a, b):\n    return a + b\n"
    )
    tests = project / "tests"
    tests.mkdir()
    (tests / "test_thing.py").write_text(
        "from pkg.thing import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n"
    )


def test_apply_rolls_back_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC1, AC2: on any exception during apply, the tests/ tree is left
    byte-identical to its pre-call state and the exception is re-raised.
    """
    project = tmp_path / "proj"
    project.mkdir()
    _make_corpus(project)
    _git_init(project)
    before = _tree_hash(project / "tests")

    def _boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("forced stage failure")

    monkeypatch.setattr(pipeline, "_run_iterations", _boom)

    with pytest.raises(RuntimeError):
        run(project, apply=True)

    assert _tree_hash(project / "tests") == before


def test_apply_failure_does_not_leak_backup_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The ``axm_fix_backup_*`` tmpdir must be discarded on EVERY path.

    Regression: ``_discard_snapshot`` used to run only in the success
    ``else`` branch, so each failed/rolled-back apply leaked a full copy of
    ``tests/`` in the system temp. The discard now lives in a ``finally``.
    """
    project = tmp_path / "proj"
    project.mkdir()
    _make_corpus(project)
    _git_init(project)

    # The pipeline snapshots ``tests/`` into ``tempfile.mkdtemp(prefix=
    # "axm_fix_backup_")``; assert no such tmpdir survives a failed apply.
    temp_root = Path(tempfile.gettempdir())
    before = set(temp_root.glob("axm_fix_backup_*"))

    def _boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("forced stage failure")

    monkeypatch.setattr(pipeline, "_run_iterations", _boom)

    with pytest.raises(Exception):  # noqa: B017
        run(project, apply=True)

    leaked = set(temp_root.glob("axm_fix_backup_*")) - before
    assert not leaked, f"backup snapshot leaked on failure: {leaked}"


def test_apply_rejects_uncollectable_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC5: if the resulting tests/ tree cannot be collected by pytest, the
    apply is rolled back, a structured error surfaces, and the tree restored.
    """
    project = tmp_path / "proj"
    project.mkdir()
    _make_corpus(project)
    _git_init(project)
    before = _tree_hash(project / "tests")

    def _corrupt(
        project_path: Path,
        *,
        apply: bool,
        rules: set[str],
        report: object,
        warnings: list[str],
    ) -> None:
        # Mutate the (staged) tree into an un-collectable state.
        broken = project_path / "tests" / "test_broken.py"
        broken.write_text("def test( :\n    pass\n")

    monkeypatch.setattr(pipeline, "_run_iterations", _corrupt)

    with pytest.raises(Exception):  # noqa: B017
        run(project, apply=True)

    assert _tree_hash(project / "tests") == before
