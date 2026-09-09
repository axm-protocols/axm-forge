"""Unit tests for the consolidated core commit-spec validator (AC1).

The validator used by ``tools/commit.py`` is a pure function returning
``(spec, err)``. It requires a non-empty ``message`` and a non-empty ``files``
list before any staging operation.
"""

from __future__ import annotations

from axm_git.core.commit_spec import validate_commit_spec


def test_validate_rejects_empty_message() -> None:
    """AC1: a spec without a (non-empty) message is rejected."""
    spec = {"message": "", "files": ["a.py"]}
    result, err = validate_commit_spec(spec)
    assert result is None
    assert err is not None
    assert err != ""


def test_validate_rejects_empty_files() -> None:
    """AC1: a spec with an empty files list is rejected (stricter contract)."""
    spec = {"message": "feat: x", "files": []}
    result, err = validate_commit_spec(spec)
    assert result is None
    assert err is not None
    assert err != ""


def test_validate_accepts_well_formed_spec() -> None:
    """AC1: a spec with a message and at least one file is accepted."""
    spec = {"message": "feat: x", "files": ["a.py"]}
    result, err = validate_commit_spec(spec)
    assert err is None
    assert result is spec
