from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from axm_audit.core.rules.practices.docstring_coverage import DocstringCoverageRule


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


@pytest.fixture
def src_dir(tmp_path: Path) -> Path:
    """Return a src directory inside tmp_path."""
    d = tmp_path / "src"
    d.mkdir()
    return d


def _write__from_docstring_coverage_filters(src_dir: Path, code: str) -> None:
    """Write a Python file into the src directory."""
    (src_dir / "mod.py").write_text(textwrap.dedent(code))


def test_setter_not_counted(rule: DocstringCoverageRule, src_dir: Path) -> None:
    """A @x.setter method without a docstring is not in missing and not in total."""
    _write__from_docstring_coverage_filters(
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
    _write__from_docstring_coverage_filters(
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
    _write__from_docstring_coverage_filters(
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


def test_abstract_override_skipped(rule: DocstringCoverageRule, src_dir: Path) -> None:
    """Override of a documented abstractmethod in same file is not in missing."""
    _write__from_docstring_coverage_filters(
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
    _write__from_docstring_coverage_filters(
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
    _write__from_docstring_coverage_filters(
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


def test_orphan_setter_still_skipped(
    rule: DocstringCoverageRule, src_dir: Path
) -> None:
    """A setter without a matching @property getter is still skipped."""
    _write__from_docstring_coverage_filters(
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
    _write__from_docstring_coverage_filters(
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


class TestDocstringCoverageRuleIntegration:
    """Tests for DocstringCoverageRule (real I/O)."""

    def test_fully_documented_passes(self, tmp_path: Path) -> None:
        """All public functions with docstrings should pass."""
        from axm_audit.core.rules.practices.docstring_coverage import (
            DocstringCoverageRule,
        )

        src = tmp_path / "src"
        src.mkdir()
        (src / "documented.py").write_text('''
def public_func() -> None:
    """This function has a docstring."""
    pass

def another_public() -> str:
    """This one too."""
    return "hello"
''')

        rule = DocstringCoverageRule()
        result = rule.check(tmp_path)
        assert result.passed is True
        assert result.details is not None
        assert result.details["coverage"] >= 0.80

    def test_missing_docstrings_fails(self, tmp_path: Path) -> None:
        """Functions without docstrings should reduce coverage."""
        from axm_audit.core.rules.practices.docstring_coverage import (
            DocstringCoverageRule,
        )

        src = tmp_path / "src"
        src.mkdir()
        (src / "undocumented.py").write_text('''
def func_one() -> None:
    pass

def func_two() -> None:
    pass

def func_three() -> None:
    pass

def func_four() -> None:
    """Only this one has a docstring."""
    pass
''')

        rule = DocstringCoverageRule()
        result = rule.check(tmp_path)
        assert result.passed is False
        assert result.details is not None
        assert result.details["coverage"] < 0.80

    def test_private_functions_ignored(self, tmp_path: Path) -> None:
        """Private functions (starting with _) should not count."""
        from axm_audit.core.rules.practices.docstring_coverage import (
            DocstringCoverageRule,
        )

        src = tmp_path / "src"
        src.mkdir()
        (src / "private.py").write_text('''
def public_func() -> None:
    """Documented public function."""
    pass

def _private_helper() -> None:
    # No docstring but should be ignored
    pass
''')

        rule = DocstringCoverageRule()
        result = rule.check(tmp_path)
        assert result.passed is True


class TestDocstringMissingDetail:
    """Tests for missing docstring listing (no cap, all items shown)."""

    def test_missing_no_cap(self, tmp_path: Path) -> None:
        """All missing docstrings are returned, not capped at 10."""
        from axm_audit.core.rules.practices.docstring_coverage import (
            DocstringCoverageRule,
        )

        src = tmp_path / "src"
        src.mkdir()
        # 15 undocumented + 1 documented = 6.25% coverage → fails
        funcs = "\n".join(f"def func_{i}() -> None:\n    pass\n" for i in range(15))
        funcs += '\ndef documented() -> None:\n    """Has a docstring."""\n    pass\n'
        (src / "many.py").write_text(funcs)

        rule = DocstringCoverageRule()
        result = rule.check(tmp_path)
        assert result.details is not None
        assert len(result.details["missing"]) == 15

    def test_missing_list_contains_locations(self, tmp_path: Path) -> None:
        """Each missing entry has file:function format."""
        from axm_audit.core.rules.practices.docstring_coverage import (
            DocstringCoverageRule,
        )

        src = tmp_path / "src"
        src.mkdir()
        (src / "mod.py").write_text("def foo() -> None:\n    pass\n")

        rule = DocstringCoverageRule()
        result = rule.check(tmp_path)
        assert result.details is not None
        assert any("foo" in m for m in result.details["missing"])

    def test_fully_documented_empty_missing(self, tmp_path: Path) -> None:
        """100% coverage returns empty missing list."""
        from axm_audit.core.rules.practices.docstring_coverage import (
            DocstringCoverageRule,
        )

        src = tmp_path / "src"
        src.mkdir()
        (src / "ok.py").write_text('def ok() -> None:\n    """Ok."""\n    pass\n')

        rule = DocstringCoverageRule()
        result = rule.check(tmp_path)
        assert result.details is not None
        assert result.details["missing"] == []
