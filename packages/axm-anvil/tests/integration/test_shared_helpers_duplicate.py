from __future__ import annotations

import pytest

from axm_anvil.core.move import move_symbols


@pytest.fixture
def shared_helper_fixture(tmp_path):
    source = tmp_path / "src.py"
    target = tmp_path / "tgt.py"
    source.write_text(
        "def _shared():\n"
        "    return 42\n"
        "\n"
        "def moved_A():\n"
        "    return _shared()\n"
        "\n"
        "def remaining_B():\n"
        "    return _shared()\n"
    )
    target.write_text("")
    return tmp_path, source, target


@pytest.mark.integration
def test_shared_helper_duplicate_mode_default(shared_helper_fixture):
    root, source, target = shared_helper_fixture
    plan = move_symbols(source, target, ["moved_A"], workspace_root=root)
    assert "_shared" in target.read_text()
    assert "_shared" in source.read_text()
    assert any("Helper '_shared' is also used by" in w for w in plan.warnings)


@pytest.mark.integration
def test_shared_helper_duplicate_mode_explicit(shared_helper_fixture):
    root, source, target = shared_helper_fixture
    plan = move_symbols(
        source,
        target,
        ["moved_A"],
        shared_helpers="duplicate",
        workspace_root=root,
    )
    assert "_shared" in target.read_text()
    assert "_shared" in source.read_text()
    assert any("Helper '_shared' is also used by" in w for w in plan.warnings)


@pytest.mark.integration
def test_non_shared_helper_no_warning(tmp_path):
    source = tmp_path / "src.py"
    target = tmp_path / "tgt.py"
    source.write_text(
        "def _only_moved():\n"
        "    return 1\n"
        "\n"
        "def moved_A():\n"
        "    return _only_moved()\n"
        "\n"
        "def remaining_B():\n"
        "    return 2\n"
    )
    target.write_text("")
    plan = move_symbols(source, target, ["moved_A"], workspace_root=tmp_path)
    assert not any("also used by" in w for w in plan.warnings)
    assert "_only_moved" not in source.read_text()
    assert "_only_moved" in target.read_text()


@pytest.mark.integration
def test_transitive_shared_helper_detected(tmp_path):
    source = tmp_path / "src.py"
    target = tmp_path / "tgt.py"
    source.write_text(
        "def _a():\n"
        "    return 1\n"
        "\n"
        "def _b():\n"
        "    return _a()\n"
        "\n"
        "def moved_A():\n"
        "    return _a()\n"
        "\n"
        "def remaining_B():\n"
        "    return _b()\n"
    )
    target.write_text("")
    plan = move_symbols(source, target, ["moved_A"], workspace_root=tmp_path)
    assert "_a" in target.read_text()
    assert "_a" in source.read_text()
    assert any("Helper '_a' is also used by" in w for w in plan.warnings)
