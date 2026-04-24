from __future__ import annotations

from axm_audit.formatters import format_agent_text


def test_format_agent_text_with_verdicts_no_keyerror() -> None:
    data = {
        "score": 80,
        "grade": "B",
        "passed": [],
        "failed": [
            {
                "rule_id": "tautologies",
                "message": "found",
                "metadata": {
                    "verdicts": [
                        {
                            "test": "step_n2_import_smoke",
                            "verdict": "DELETE",
                            "file": "t.py",
                            "line": 1,
                        },
                    ],
                },
            },
        ],
    }
    out = format_agent_text(data)
    assert isinstance(out, str)
    assert out


def test_format_agent_text_with_clusters_no_keyerror() -> None:
    data = {
        "score": 80,
        "grade": "B",
        "passed": [],
        "failed": [
            {
                "rule_id": "duplicates",
                "message": "found",
                "metadata": {
                    "clusters": [
                        {
                            "signal": "signal1_call_assert",
                            "members": [
                                {"test": "t1", "file": "f.py", "line": 1},
                            ],
                        },
                    ],
                    "buckets": {"signal1_call_assert": 1},
                },
            },
        ],
    }
    out = format_agent_text(data)
    assert isinstance(out, str)
    assert out


def test_format_agent_text_backward_compat_no_metadata() -> None:
    data = {
        "score": 100,
        "grade": "A",
        "passed": [{"rule_id": "r1"}],
        "failed": [],
    }
    out = format_agent_text(data)
    assert isinstance(out, str)
    assert "r1" in out
