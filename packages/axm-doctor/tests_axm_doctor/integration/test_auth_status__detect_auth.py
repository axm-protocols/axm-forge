"""Integration tests for the public authentication-status tool."""

from __future__ import annotations

import pytest

from axm_doctor import AuthStatusTool, collect_credential_provenance


@pytest.mark.integration
def test_auth_status_publishes_live_credential_provenance() -> None:
    """AC1: auth_status publishes exactly the live credential coordinates."""
    expected_rows = collect_credential_provenance()

    result = AuthStatusTool().execute()

    assert result.success is True
    credentials = result.data["credentials"]
    assert set(credentials) == {row.coordinate for row in expected_rows}
    assert all(set(entry) == {"layer", "present"} for entry in credentials.values())
