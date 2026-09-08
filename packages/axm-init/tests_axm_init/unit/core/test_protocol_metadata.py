from __future__ import annotations

import tomllib

from axm_init.core.protocol_metadata import merge_protocol_metadata
from axm_init.models.protocol_scaffold import ProtocolScaffoldDecl


def _declaration() -> ProtocolScaffoldDecl:
    return ProtocolScaffoldDecl.model_validate(
        {
            "domain": "orchestrate",
            "unit": "daily_digest",
            "action": "exec",
            "contracts": [
                {"name": "digest_input"},
                {"name": "digest_report"},
            ],
            "nodes": [
                {
                    "name": "write_summary",
                    "contract": "digest_report",
                    "prompt": "write_summary",
                }
            ],
            "prompts": [
                {"name": "write_summary", "text": "TODO: skeleton"},
            ],
            "phases": [],
            "ticket": {
                "ticket_type": "orchestrate.daily_digest",
                "input_contract": "digest_input",
            },
        }
    )


def _merge(metadata: str, declaration: ProtocolScaffoldDecl) -> str:
    protocol_metadata = merge_protocol_metadata
    return protocol_metadata(metadata, declaration)


def test_preserves_unrelated_formatted_metadata_while_adding_draft_profile() -> None:
    """AC1: add the draft profile without reformatting unrelated metadata."""
    unrelated_fragment = """# This comment and spacing belong to the caller
[project]
name = "example"
description   = "spacing is intentional" # keep this comment

[tool.foreign]
enabled = true
"""
    merged = _merge(unrelated_fragment, _declaration())

    assert unrelated_fragment in merged
    assert tomllib.loads(merged)["tool"]["axm-init"]["protocols"] == {
        "schema_version": 1,
        "domain": "orchestrate",
        "units": [
            {
                "name": "daily_digest",
                "protocols": [
                    {
                        "action": "exec",
                        "state": "draft",
                        "contracts": ["digest_input", "digest_report"],
                        "nodes": ["write_summary"],
                        "prompts": ["write_summary"],
                        "phases": [],
                        "ticket_type": "orchestrate.daily_digest",
                        "input_contract": "digest_input",
                    }
                ],
            }
        ],
    }


def test_repeated_merge_is_byte_idempotent() -> None:
    """AC2: replaying one declaration is byte-identical and duplicate-free."""
    first = _merge('[project]\nname = "example"\n', _declaration())
    second = _merge(first, _declaration())

    assert second == first
    profile = tomllib.loads(second)["tool"]["axm-init"]["protocols"]
    assert len(profile["units"]) == 1
    assert len(profile["units"][0]["protocols"]) == 1
