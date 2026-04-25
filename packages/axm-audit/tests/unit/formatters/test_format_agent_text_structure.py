from __future__ import annotations

from axm_audit.formatters import format_agent_text


def test_passed_chunked_5_per_line() -> None:
    rule_ids = [f"R{i:02d}" for i in range(12)]
    data = {
        "score": 100,
        "grade": "A",
        "passed": [{"rule_id": rid} for rid in rule_ids],
        "failed": [],
    }

    text = format_agent_text(data)
    check_lines = [line for line in text.splitlines() if line.startswith("\u2713 ")]

    assert len(check_lines) == 3
    assert check_lines[0] == "\u2713 " + " ".join(rule_ids[0:5])
    assert check_lines[1] == "\u2713 " + " ".join(rule_ids[5:10])
    assert check_lines[2] == "\u2713 " + " ".join(rule_ids[10:12])


def test_section_order_text_meta_fix() -> None:
    data = {
        "score": 50,
        "grade": "C",
        "passed": [],
        "failed": [
            {
                "rule_id": "X01",
                "message": "failure",
                "text": "line-A\nline-B",
                "metadata": {
                    "verdicts": [
                        {
                            "verdict": "FLAKY",
                            "test": "t1",
                            "file": "f.py",
                            "line": 10,
                        }
                    ],
                    "clusters": [{"signal": "timeout", "members": ["a", "b", "c"]}],
                },
                "fix_hint": "do the thing",
            }
        ],
    }

    lines = format_agent_text(data).splitlines()
    indented = [line for line in lines if line.startswith("  ")]

    text_a = indented.index("  line-A")
    text_b = indented.index("  line-B")
    verdict_idx = next(
        i for i, line in enumerate(indented) if line.startswith("  [FLAKY]")
    )
    cluster_idx = next(
        i for i, line in enumerate(indented) if line.startswith("  [timeout]")
    )
    fix_idx = indented.index("  fix: do the thing")

    assert text_a < text_b < verdict_idx < cluster_idx < fix_idx
