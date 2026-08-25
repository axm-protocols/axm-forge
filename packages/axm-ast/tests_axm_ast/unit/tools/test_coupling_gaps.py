from __future__ import annotations

import types


def _site(f: str, n: int) -> types.SimpleNamespace:
    return types.SimpleNamespace(file=f, line=n, why="w", confidence="high")


def test_render_text_emits_caveat_and_counts() -> None:
    """AC3: rendered text carries the lower-bound caveat plus protocol/value counts."""
    from axm_ast.tools.coupling_gaps import _render_text

    protocol_sites = [
        _site("a.py", 1),
        _site("b.py", 2),
        _site("c.py", 3),
    ]
    value_sites = [_site("d.py", 4), _site("e.py", 5)]
    result = {
        "reference_coupled": {"Foo": []},
        "protocol_coupled": {"Foo": protocol_sites},
        "value_coupled": {"Foo": value_sites},
    }

    text = _render_text(result)

    assert "lower-bound" in text.lower()
    assert "3" in text
    assert "2" in text
