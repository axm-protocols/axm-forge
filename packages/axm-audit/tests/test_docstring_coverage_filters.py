from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from axm_audit.core.rules.practices import DocstringCoverageRule


@pytest.fixture
def rule() -> DocstringCoverageRule:
    return DocstringCoverageRule()


@pytest.fixture
def src_dir(tmp_path: Path) -> Path:
    """Return a src directory inside tmp_path."""
    d = tmp_path / "src"
    d.mkdir()
    return d


def _write(src_dir: Path, code: str) -> None:
    """Write a Python file into the src directory."""
    (src_dir / "mod.py").write_text(textwrap.dedent(code))


# --- Unit tests: setter / deleter filtering ---


def test_setter_not_counted(rule: DocstringCoverageRule, src_dir: Path) -> None:
    """A @x.setter method without a docstring is not in missing and not in total."""
    _write(
        src_dir,
        '''\
        class Foo:
            @property
            def value(self):
                """The value."""
                return self._value

            @value.setter
            def value(self, val):
                self._value = val
        ''',
    )
    documented, missing = rule._analyze_docstrings(src_dir)
    # The setter should not appear in missing at all
    assert "mod.py:value" not in missing
    # Only the getter counts; getter has docstring so documented >= 1
    assert documented >= 1


def test_deleter_not_counted(rule: DocstringCoverageRule, src_dir: Path) -> None:
    """A @x.deleter method without a docstring is not in missing and not in total."""
    _write(
        src_dir,
        '''\
        class Foo:
            @property
            def value(self):
                """The value."""
                return self._value

            @value.deleter
            def value(self):
                del self._value
        ''',
    )
    documented, missing = rule._analyze_docstrings(src_dir)
    # Deleter should not appear in missing
    assert "mod.py:value" not in missing
    assert documented >= 1


def test_getter_still_counted(rule: DocstringCoverageRule, src_dir: Path) -> None:
    """A @property getter without a docstring IS in missing and counted in total."""
    _write(
        src_dir,
        """\
        class Foo:
            @property
            def value(self):
                return self._value
        """,
    )
    _documented, missing = rule._analyze_docstrings(src_dir)
    assert "mod.py:value" in missing


# --- Unit tests: abstract override filtering ---


def test_abstract_override_skipped(rule: DocstringCoverageRule, src_dir: Path) -> None:
    """Override of a documented abstractmethod in same file is not in missing."""
    _write(
        src_dir,
        '''\
        from abc import ABC, abstractmethod

        class Base(ABC):
            @abstractmethod
            def process(self):
                """Process data."""
                ...

        class Concrete(Base):
            def process(self):
                return 42
        ''',
    )
    _documented, missing = rule._analyze_docstrings(src_dir)
    # The override should not be in missing since parent abstract has docstring
    override_entries = [m for m in missing if m == "mod.py:process"]
    assert override_entries == []


def test_abstract_override_no_parent_docstring(
    rule: DocstringCoverageRule, src_dir: Path
) -> None:
    """Override of undocumented abstractmethod IS in missing."""
    _write(
        src_dir,
        """\
        from abc import ABC, abstractmethod

        class Base(ABC):
            @abstractmethod
            def process(self):
                ...

        class Concrete(Base):
            def process(self):
                return 42
        """,
    )
    _documented, missing = rule._analyze_docstrings(src_dir)
    # Both the abstract method and the override should be in missing
    process_entries = [m for m in missing if m == "mod.py:process"]
    assert len(process_entries) >= 1


def test_non_abstract_override_still_counted(
    rule: DocstringCoverageRule, src_dir: Path
) -> None:
    """Override of a non-abstract method without docstring IS in missing."""
    _write(
        src_dir,
        '''\
        class Base:
            def process(self):
                """Process data."""
                return 1

        class Child(Base):
            def process(self):
                return 2
        ''',
    )
    _documented, missing = rule._analyze_docstrings(src_dir)
    # The override of a non-abstract method should still be in missing
    process_entries = [m for m in missing if m == "mod.py:process"]
    assert len(process_entries) >= 1


# --- Edge cases ---


def test_orphan_setter_still_skipped(
    rule: DocstringCoverageRule, src_dir: Path
) -> None:
    """A setter without a matching @property getter is still skipped."""
    _write(
        src_dir,
        """\
        class Foo:
            @value.setter
            def value(self, val):
                self._value = val
        """,
    )
    _documented, missing = rule._analyze_docstrings(src_dir)
    assert "mod.py:value" not in missing


def test_property_getter_with_docstring_setter_without(
    rule: DocstringCoverageRule, src_dir: Path
) -> None:
    """Getter documented + setter undocumented = getter counted, setter skipped."""
    _write(
        src_dir,
        '''\
        class Foo:
            @property
            def value(self):
                """The value property."""
                return self._value

            @value.setter
            def value(self, val):
                self._value = val
        ''',
    )
    documented, missing = rule._analyze_docstrings(src_dir)
    # Getter is documented, setter is skipped entirely
    assert documented >= 1
    assert "mod.py:value" not in missing
