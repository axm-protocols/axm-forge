"""Versioned write-contract errors use the same boundary as legacy headers."""

import json

import pytest

from axm_mcp.session_contracts import (
    WriteContractHeaderError,
    parse_write_contract_header,
)


@pytest.mark.parametrize(
    "payload",
    [
        {"version": 2, "contracts": []},
        {"version": 3, "contracts": [{"execution_root": "/tmp"}]},
        {
            "version": 2,
            "contracts": [{"execution_root": "/tmp", "allowed_prefixes": None}],
        },
        {"version": 2, "contracts": [{"execution_root": "/tmp"}], "extra": True},
    ],
)
def test_invalid_versioned_contract_is_rejected(payload: dict[str, object]) -> None:
    with pytest.raises(WriteContractHeaderError):
        parse_write_contract_header(json.dumps(payload))
