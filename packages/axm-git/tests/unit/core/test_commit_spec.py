"""Unit tests for the consolidated core commit-spec validator (AC1).

The single source-of-truth validator lives in ``axm_git.core.commit_spec`` and
is shared by both ``tools/commit.py`` and ``hooks/commit_phase.py``.  It is a
pure function returning ``(spec, err)`` — each surface wraps the error string
in its own result type.  The merged contract is the STRICTER of the two prior
copies: require a non-empty ``message`` AND a non-empty ``files`` list.
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
