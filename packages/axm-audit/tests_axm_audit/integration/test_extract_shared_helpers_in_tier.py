"""Integration tests for extract_shared_helpers_in_tier extraction branches."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.core.fix.extract_helpers import extract_shared_helpers_in_tier

pytestmark = pytest.mark.integration


def _make_tier(tmp_path: Path, files: dict[str, str]) -> tuple[Path, Path]:
    """Write *files* (relative to the project root) and return (project, tier)."""
    project = tmp_path / "proj"
    tier_dir = project / "tests" / "integration"
    tier_dir.mkdir(parents=True)
    for rel, content in files.items():
        target = project / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    return project, tier_dir


def test_consolidates_duplicate_constant_into_helpers(tmp_path: Path) -> None:
    """An UPPER constant duplicated across files is promoted to _helpers.py.

    Covers the Assign classification branch, the constant-hash grouping, and
    the assign-strip + import-injection path of strip_def_and_inject_import.
    """
    const = "TIMEOUT = 30\n\n\n"
    project, tier = _make_tier(
        tmp_path,
        {
            "tests/integration/test_a.py": const
            + "def test_a():\n    assert TIMEOUT == 30\n",
            "tests/integration/test_b.py": const
            + "def test_b():\n    assert TIMEOUT == 30\n",
        },
    )

    msgs = extract_shared_helpers_in_tier(project, tier)

    helpers = (tier / "_helpers.py").read_text()
    assert "TIMEOUT = 30" in helpers
    src_a = (tier / "test_a.py").read_text()
    assert "TIMEOUT = 30" not in src_a
    assert "from tests.integration._helpers import TIMEOUT" in src_a
    assert any("extracted helper `TIMEOUT`" in m for m in msgs)


def test_consolidates_duplicate_class_into_helpers(tmp_path: Path) -> None:
    """A non-Test class duplicated across files is promoted as a pure helper."""
    klass = "class Box:\n    value = 1\n\n\n"
    project, tier = _make_tier(
        tmp_path,
        {
            "tests/integration/test_a.py": klass
            + "def test_a():\n    assert Box.value == 1\n",
            "tests/integration/test_b.py": klass
            + "def test_b():\n    assert Box.value == 1\n",
        },
    )

    msgs = extract_shared_helpers_in_tier(project, tier)

    assert "class Box" in (tier / "_helpers.py").read_text()
    assert "class Box" not in (tier / "test_a.py").read_text()
    assert any("extracted helper `Box`" in m for m in msgs)


def test_consolidates_duplicate_fixture_into_conftest(tmp_path: Path) -> None:
    """A duplicated @pytest.fixture lands in the tier's conftest.py, no import.

    Covers _emit_one_fixture, the conftest flush/backfill branch, and the
    strip_def_only path (fixtures are auto-discovered, never imported).
    """
    fixture = "import pytest\n\n\n@pytest.fixture\ndef sample():\n    return 42\n\n\n"
    project, tier = _make_tier(
        tmp_path,
        {
            "tests/integration/test_a.py": fixture
            + "def test_a(sample):\n    assert sample == 42\n",
            "tests/integration/test_b.py": fixture
            + "def test_b(sample):\n    assert sample == 42\n",
        },
    )

    msgs = extract_shared_helpers_in_tier(project, tier)

    conftest = (project / "tests" / "conftest.py").read_text()
    assert "def sample" in conftest
    assert "@pytest.fixture" in conftest
    src_a = (tier / "test_a.py").read_text()
    assert "def sample" not in src_a
    assert "import sample" not in src_a
    assert not (tier / "_helpers.py").exists()
    assert any("extracted fixture `sample`" in m for m in msgs)


def test_constant_referencing_file_dunder_is_skipped(tmp_path: Path) -> None:
    """A constant whose value reads __file__ is location-bound, never extracted."""
    const = "DATA_DIR = __file__\n\n\n"
    project, tier = _make_tier(
        tmp_path,
        {
            "tests/integration/test_a.py": const
            + "def test_a():\n    assert DATA_DIR\n",
            "tests/integration/test_b.py": const
            + "def test_b():\n    assert DATA_DIR\n",
        },
    )

    msgs = extract_shared_helpers_in_tier(project, tier)

    assert not (tier / "_helpers.py").exists()
    assert "DATA_DIR = __file__" in (tier / "test_a.py").read_text()
    assert msgs == []


def test_single_occurrence_helper_is_not_extracted(tmp_path: Path) -> None:
    """A helper present in only one file stays put (len(files) < 2 guard)."""
    project, tier = _make_tier(
        tmp_path,
        {
            "tests/integration/test_a.py": (
                "def _solo(x):\n    return x\n\n\n"
                "def test_a():\n    assert _solo(1) == 1\n"
            ),
            "tests/integration/test_b.py": "def test_b():\n    assert True\n",
        },
    )

    msgs = extract_shared_helpers_in_tier(project, tier)

    assert not (tier / "_helpers.py").exists()
    assert "def _solo" in (tier / "test_a.py").read_text()
    assert msgs == []


def test_cascading_skip_when_dependency_is_ambiguous(tmp_path: Path) -> None:
    """A duplicated helper referencing an ambiguous helper is dropped, not moved.

    ``_base`` has divergent bodies (ambiguous skip); ``_wrap`` is byte-identical
    everywhere but calls ``_base`` — extracting it alone would NameError, so it
    cascades into a skip rather than landing in _helpers.py.
    """
    wrap = "def _wrap(x):\n    return _base(x) + 1\n\n\n"
    project, tier = _make_tier(
        tmp_path,
        {
            "tests/integration/test_a.py": (
                "def _base(x):\n    return x * 2\n\n\n"
                + wrap
                + "def test_a():\n    assert _wrap(1) == 3\n"
            ),
            "tests/integration/test_b.py": (
                "def _base(x):\n    return x + 100\n\n\n"
                + wrap
                + "def test_b():\n    assert _wrap(1) == 102\n"
            ),
        },
    )

    msgs = extract_shared_helpers_in_tier(project, tier)

    assert not (tier / "_helpers.py").exists()
    assert "def _wrap" in (tier / "test_a.py").read_text()
    blob = "\n".join(msgs)
    assert "cascading skip `_wrap`" in blob
    assert "ambiguous helper `_base`" in blob


def test_syntax_error_file_is_skipped_during_scan(tmp_path: Path) -> None:
    """An unparseable file is silently skipped; valid duplicates still extract."""
    helper = "def _twice(x):\n    return x * 2\n\n\n"
    project, tier = _make_tier(
        tmp_path,
        {
            "tests/integration/test_a.py": helper
            + "def test_a():\n    assert _twice(1) == 2\n",
            "tests/integration/test_b.py": helper
            + "def test_b():\n    assert _twice(2) == 4\n",
            "tests/integration/test_broken.py": "def test_broken(:\n    pass\n",
        },
    )

    msgs = extract_shared_helpers_in_tier(project, tier)

    assert "def _twice" in (tier / "_helpers.py").read_text()
    # The broken file is untouched by extraction.
    assert (tier / "test_broken.py").read_text() == "def test_broken(:\n    pass\n"
    assert any("extracted helper `_twice`" in m for m in msgs)


def test_divergent_bodies_emit_ambiguous_skip_message(tmp_path: Path) -> None:
    """Divergent helper bodies are reported as ambiguous, naming each file."""
    project, tier = _make_tier(
        tmp_path,
        {
            "tests/integration/test_a.py": (
                "def _calc(x):\n    return x * 2\n\n\n"
                "def test_a():\n    assert _calc(1) == 2\n"
            ),
            "tests/integration/test_b.py": (
                "def _calc(x):\n    return x + 9\n\n\n"
                "def test_b():\n    assert _calc(1) == 10\n"
            ),
        },
    )

    msgs = extract_shared_helpers_in_tier(project, tier)

    assert not (tier / "_helpers.py").exists()
    blob = "\n".join(msgs)
    assert "ambiguous helper `_calc`" in blob
    assert "test_a.py" in blob and "test_b.py" in blob


def test_existing_helpers_module_appends_new_helper(tmp_path: Path) -> None:
    """A new duplicate is appended to a pre-existing _helpers.py without loss."""
    helper = "def _added(x):\n    return x\n\n\n"
    project, tier = _make_tier(
        tmp_path,
        {
            "tests/integration/_helpers.py": (
                "from __future__ import annotations\n\n\n"
                "def _preexisting():\n    return 0\n"
            ),
            "tests/integration/test_a.py": helper
            + "def test_a():\n    assert _added(1) == 1\n",
            "tests/integration/test_b.py": helper
            + "def test_b():\n    assert _added(2) == 2\n",
        },
    )

    extract_shared_helpers_in_tier(project, tier)

    helpers = (tier / "_helpers.py").read_text()
    assert "def _preexisting" in helpers
    assert "def _added" in helpers
