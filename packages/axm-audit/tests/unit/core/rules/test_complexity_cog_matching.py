"""Unit tests for CC/Cog key pairing warnings in ``ComplexityRule.check``.

Driven through the public boundary with the radon API and the cognitive
map stubbed in-memory (no real I/O), per the test-spec rule: never call
the ``_check_via_api`` / ``_cognitive_via_api`` privates directly.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

import pytest

from axm_audit.core.rules import complexity as complexity_mod
from axm_audit.core.rules.complexity import ComplexityRule


class _FakeBlock:
    """Stand-in for a radon CC block."""

    def __init__(self, classname: str, name: str, cc: int) -> None:
        self.classname = classname
        self.name = name
        self.complexity = cc


def _fake_radon(
    blocks: list[_FakeBlock],
) -> tuple[Callable[[str], list[_FakeBlock]], Callable[[int], str]]:
    """Return ``(cc_visit, cc_rank)`` stand-ins mirroring radon's API."""

    def cc_visit(_source: str) -> list[_FakeBlock]:
        return blocks

    def cc_rank(cc: int) -> str:
        return "C" if cc >= 11 else "A"

    return cc_visit, cc_rank


def _write_pkg(tmp_path: Path) -> None:
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("", encoding="utf-8")
    (src / "mod.py").write_text(
        "class A:\n    def run(self):\n        return 1\n", encoding="utf-8"
    )


def test_unmatched_cog_logs_warning(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """AC2: a CC block with no matching Cog entry logs a warning naming it.

    The cognitive layer is enabled (``cog_disabled=False``) but its map
    lacks the block's qualified key — the score must not be silently
    treated as 0 without a trace.
    """
    _write_pkg(tmp_path)

    block = _FakeBlock("A", "run", 12)
    monkeypatch.setattr(
        complexity_mod, "_try_import_radon", lambda: _fake_radon([block])
    )
    # Cognitive enabled but empty -> A.run has no match.
    monkeypatch.setattr(
        complexity_mod, "_compute_cognitive_map", lambda _src: ({}, False)
    )

    with caplog.at_level(logging.WARNING, logger=complexity_mod.logger.name):
        ComplexityRule().check(tmp_path)

    messages = "\n".join(r.getMessage() for r in caplog.records)
    assert "A.run" in messages
    assert "mod.py" in messages


def test_no_warning_when_cog_disabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """AC2: when the cognitive layer is disabled, a missing entry is expected.

    No per-block warning should fire — the absence is structural, not a
    real pairing failure.
    """
    _write_pkg(tmp_path)

    block = _FakeBlock("A", "run", 12)
    monkeypatch.setattr(
        complexity_mod, "_try_import_radon", lambda: _fake_radon([block])
    )
    monkeypatch.setattr(
        complexity_mod, "_compute_cognitive_map", lambda _src: ({}, True)
    )

    with caplog.at_level(logging.WARNING, logger=complexity_mod.logger.name):
        ComplexityRule().check(tmp_path)

    messages = "\n".join(r.getMessage() for r in caplog.records)
    assert "A.run" not in messages
