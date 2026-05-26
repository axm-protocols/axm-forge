from __future__ import annotations

from axm_anvil.core.plan import SharedHelpersError


def test_shared_helpers_error_exception_dataclass():
    exc = SharedHelpersError(shared_helpers=["_h1", "_h2"])
    message = str(exc)
    assert "_h1" in message
    assert "_h2" in message
