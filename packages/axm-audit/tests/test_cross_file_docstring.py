from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from axm_audit.core.rules.practices import DocstringCoverageRule


@pytest.fixture
def rule() -> DocstringCoverageRule:
    return DocstringCoverageRule()


def _write(path: Path, code: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(code))


# ── Unit tests ──────────────────────────────────────────────────────────


def test_cross_file_abstract_override_skipped(
    rule: DocstringCoverageRule, tmp_path: Path
) -> None:
    """Override of a documented @abstractmethod from another file is NOT missing."""
    _write(
        tmp_path / "base.py",
        '''\
        from abc import ABC, abstractmethod

        class Base(ABC):
            @abstractmethod
            def process(self):
                """Process data."""
        ''',
    )
    _write(
        tmp_path / "impl.py",
        """\
        from base import Base

        class Impl(Base):
            def process(self):
                return 42
        """,
    )
    _documented, missing = rule._analyze_docstrings(tmp_path)
    assert not any("impl.py:process" in m for m in missing)


def test_cross_file_abstract_no_parent_docstring(
    rule: DocstringCoverageRule, tmp_path: Path
) -> None:
    """Override of an @abstractmethod WITHOUT docstring IS counted as missing."""
    _write(
        tmp_path / "base.py",
        """\
        from abc import ABC, abstractmethod

        class Base(ABC):
            @abstractmethod
            def process(self):
                ...
        """,
    )
    _write(
        tmp_path / "impl.py",
        """\
        from base import Base

        class Impl(Base):
            def process(self):
                return 42
        """,
    )
    _documented, missing = rule._analyze_docstrings(tmp_path)
    assert any("impl.py:process" in m for m in missing)


def test_same_file_still_works(rule: DocstringCoverageRule, tmp_path: Path) -> None:
    """Same-file abstract override detection continues to work (no regression)."""
    _write(
        tmp_path / "combo.py",
        '''\
        from abc import ABC, abstractmethod

        class Base(ABC):
            @abstractmethod
            def run(self):
                """Run the process."""

        class Concrete(Base):
            def run(self):
                return 1
        ''',
    )
    _documented, missing = rule._analyze_docstrings(tmp_path)
    assert not any("combo.py:run" in m for m in missing)


def test_non_abstract_cross_file_counted(
    rule: DocstringCoverageRule, tmp_path: Path
) -> None:
    """Override of a regular (non-abstract) method is counted as missing."""
    _write(
        tmp_path / "base.py",
        '''\
        class Base:
            def compute(self):
                """Compute something."""
                return 0
        ''',
    )
    _write(
        tmp_path / "impl.py",
        """\
        from base import Base

        class Child(Base):
            def compute(self):
                return 99
        """,
    )
    _documented, missing = rule._analyze_docstrings(tmp_path)
    assert any("impl.py:compute" in m for m in missing)


# ── Edge cases ──────────────────────────────────────────────────────────


def test_name_collision_across_files_counts_conservatively(
    rule: DocstringCoverageRule, tmp_path: Path
) -> None:
    """Two files define class 'Base' — ambiguous, so override is NOT skipped."""
    _write(
        tmp_path / "a.py",
        '''\
        from abc import ABC, abstractmethod

        class Base(ABC):
            @abstractmethod
            def do_work(self):
                """Do the work."""
        ''',
    )
    _write(
        tmp_path / "b.py",
        '''\
        from abc import ABC, abstractmethod

        class Base(ABC):
            @abstractmethod
            def do_work(self):
                """Also does work."""
        ''',
    )
    _write(
        tmp_path / "impl.py",
        """\
        from a import Base

        class Worker(Base):
            def do_work(self):
                return True
        """,
    )
    _documented, missing = rule._analyze_docstrings(tmp_path)
    # Ambiguous name collision — should count conservatively (don't skip)
    assert any("impl.py:do_work" in m for m in missing)


def test_reexport_via_init(rule: DocstringCoverageRule, tmp_path: Path) -> None:
    """Import via __init__.py re-export still resolves the base class."""
    pkg = tmp_path / "pkg"
    _write(
        pkg / "base.py",
        '''\
        from abc import ABC, abstractmethod

        class Strategy(ABC):
            @abstractmethod
            def execute(self):
                """Execute the strategy."""
        ''',
    )
    _write(
        pkg / "__init__.py",
        """\
        from .base import Strategy
        """,
    )
    _write(
        pkg / "concrete.py",
        """\
        from pkg import Strategy

        class MyStrategy(Strategy):
            def execute(self):
                return "done"
        """,
    )
    _documented, missing = rule._analyze_docstrings(tmp_path)
    assert not any("concrete.py:execute" in m for m in missing)


def test_circular_imports_no_infinite_loop(
    rule: DocstringCoverageRule, tmp_path: Path
) -> None:
    """Circular import references do not cause infinite loops."""
    _write(
        tmp_path / "mod_a.py",
        '''\
        from abc import ABC, abstractmethod
        from mod_b import Helper

        class Base(ABC):
            @abstractmethod
            def run(self):
                """Run it."""
        ''',
    )
    _write(
        tmp_path / "mod_b.py",
        '''\
        from mod_a import Base

        class Helper:
            def assist(self):
                """Assist."""

        class Derived(Base):
            def run(self):
                return Helper().assist()
        ''',
    )
    _documented, missing = rule._analyze_docstrings(tmp_path)
    # Should complete without hanging; override of documented abstract is skipped
    assert not any("mod_b.py:run" in m for m in missing)
