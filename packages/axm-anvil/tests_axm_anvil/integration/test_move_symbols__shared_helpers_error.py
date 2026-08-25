from __future__ import annotations

import pytest

from axm_anvil.core.move import move_symbols
from axm_anvil.core.plan import SharedHelpersError


@pytest.mark.integration
def test_shared_helper_error_mode_raises(shared_helper_fixture):
    root, source, target = shared_helper_fixture
    source_snapshot = source.read_text()
    target_snapshot = target.read_text()
    with pytest.raises(SharedHelpersError) as excinfo:
        move_symbols(
            source,
            target,
            ["moved_A"],
            shared_helpers="error",
            workspace_root=root,
        )
    assert "_shared" in excinfo.value.shared_helpers
    assert source.read_text() == source_snapshot
    assert target.read_text() == target_snapshot


@pytest.mark.integration
def test_shared_helper_error_mode_no_writes(shared_helper_fixture, mocker):
    root, source, target = shared_helper_fixture
    patched = mocker.patch("axm_anvil.core.move.batch_edit")
    with pytest.raises(SharedHelpersError):
        move_symbols(
            source,
            target,
            ["moved_A"],
            shared_helpers="error",
            workspace_root=root,
        )
    patched.assert_not_called()
