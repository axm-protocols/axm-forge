"""Integration tests for the extract_shared_helpers extraction engine.

These drive ``extract_shared_helpers_in_tier`` / ``extract_shared_helpers``
over a real ``tests/<tier>`` tree on disk (read + libcst rewrite), so they
live at the integration pyramid level. They exercise the engine branches
the unit tests (absent-path + stub synthesis) cannot reach: constant /
class / fixture extraction, ``__file__`` location skips, single-occurrence
guards, cascading skips, ambiguous-body dedup across iterations, and the
libcst strip helpers.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.core.fix.extract_helpers import (
    extract_shared_helpers,
    extract_shared_helpers_in_tier,
    extract_shared_helpers_once,
    load_or_create_conftest_module,
    load_or_create_helpers_module,
    strip_def_and_inject_import,
    strip_def_only,
)

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


def test_extract_shared_helpers_dedups_ambiguous_across_iterations(
    tmp_path: Path,
) -> None:
    """The fixed-point loop reports each ambiguous *fixture* exactly once.

    ``extract_shared_helpers`` runs ``_once`` repeatedly; a permanently
    ambiguous fixture re-surfaces on every pass (proven by calling ``_once``
    directly), but the iterating entry point must collapse it to a single
    message in the returned list.
    """
    fixture_a = (
        "import pytest\n\n\n"
        "@pytest.fixture\n"
        "def client():\n    return {'mode': 'a'}\n\n\n"
    )
    fixture_b = (
        "import pytest\n\n\n"
        "@pytest.fixture\n"
        "def client():\n    return {'mode': 'b', 'extra': 1}\n\n\n"
    )
    project, _ = _make_tier(
        tmp_path,
        {
            "tests/integration/test_a.py": (
                fixture_a + "def test_a(client):\n    assert client['mode'] == 'a'\n"
            ),
            "tests/integration/test_b.py": (
                fixture_b + "def test_b(client):\n    assert client['mode'] == 'b'\n"
            ),
        },
    )

    # A single pass already reports the divergent fixture as ambiguous.
    once_msgs = extract_shared_helpers_once(project)
    assert any("ambiguous fixture `client`" in m for m in once_msgs)

    # The fixed-point loop must not duplicate it across its iterations.
    msgs = extract_shared_helpers(project)
    ambiguous = [m for m in msgs if "ambiguous fixture `client`" in m]
    assert len(ambiguous) == 1


def test_extract_shared_helpers_promotes_then_reaches_fixed_point(
    tmp_path: Path,
) -> None:
    """The loop applies an extraction, then converges with no further changes."""
    helper = "def _shared(x):\n    return x - 1\n\n\n"
    project, tier = _make_tier(
        tmp_path,
        {
            "tests/integration/test_a.py": helper
            + "def test_a():\n    assert _shared(2) == 1\n",
            "tests/integration/test_b.py": helper
            + "def test_b():\n    assert _shared(3) == 2\n",
        },
    )

    msgs = extract_shared_helpers(project)

    assert "def _shared" in (tier / "_helpers.py").read_text()
    # Exactly one extraction message — the second pass finds nothing to move.
    assert sum("extracted helper `_shared`" in m for m in msgs) == 1


def test_existing_helpers_module_is_loaded_not_overwritten(tmp_path: Path) -> None:
    """load_or_create_helpers_module reads an existing file verbatim."""
    helpers_path = tmp_path / "_helpers.py"
    helpers_path.write_text("SENTINEL = 1\n")

    module = load_or_create_helpers_module(helpers_path, "unit", "tests.unit._helpers")

    assert module is not None
    assert "SENTINEL = 1" in module.code


def test_existing_conftest_module_is_loaded_not_overwritten(tmp_path: Path) -> None:
    """load_or_create_conftest_module reads an existing file verbatim."""
    conftest_path = tmp_path / "conftest.py"
    conftest_path.write_text("MARKER = 'kept'\n")

    module = load_or_create_conftest_module(conftest_path)

    assert module is not None
    assert "MARKER = 'kept'" in module.code


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


def test_strip_def_only_removes_function_in_place(tmp_path: Path) -> None:
    """strip_def_only deletes the named def and rewrites the file."""
    target = tmp_path / "mod.py"
    target.write_text("def keep():\n    return 1\n\n\ndef drop():\n    return 2\n")

    strip_def_only(target, "drop")

    body = target.read_text()
    assert "def keep" in body
    assert "def drop" not in body


def test_strip_def_only_no_match_leaves_file_untouched(tmp_path: Path) -> None:
    """strip_def_only is a no-op when the name is absent."""
    target = tmp_path / "mod.py"
    original = "def keep():\n    return 1\n"
    target.write_text(original)

    strip_def_only(target, "absent")

    assert target.read_text() == original


def test_strip_def_and_inject_import_no_match_injects_nothing(tmp_path: Path) -> None:
    """When the name is absent, no def is stripped and no import is injected."""
    target = tmp_path / "mod.py"
    original = "def keep():\n    return 1\n"
    target.write_text(original)

    strip_def_and_inject_import(target, "absent", "tests.unit._helpers", tmp_path)

    body = target.read_text()
    assert "import" not in body
    assert "def keep" in body


def test_strip_def_and_inject_import_places_import_after_docstring(
    tmp_path: Path,
) -> None:
    """The injected import lands below a module docstring and existing imports."""
    target = tmp_path / "mod.py"
    target.write_text(
        '"""Module doc."""\n\n'
        "import os\n\n\n"
        "def moved():\n    return os.getcwd()\n\n\n"
        "def test_it():\n    assert moved()\n"
    )

    strip_def_and_inject_import(target, "moved", "tests.unit._helpers", tmp_path)

    lines = [ln for ln in target.read_text().splitlines() if ln.strip()]
    assert "def moved" not in target.read_text()
    import_line = "from tests.unit._helpers import moved"
    assert import_line in lines
    # Import sits after the docstring and the pre-existing `import os`.
    assert lines.index(import_line) > lines.index("import os")
    assert lines.index('"""Module doc."""') < lines.index(import_line)
