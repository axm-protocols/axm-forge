"""Split from ``test_dead_code.py``."""

from axm_ast.core.dead_code import DeadSymbol, format_dead_code


def test_format_results() -> None:
    """Results → grouped output."""
    results = [
        DeadSymbol(name="foo", module_path="/a/b.py", line=10, kind="function"),
        DeadSymbol(name="bar", module_path="/a/b.py", line=20, kind="method"),
        DeadSymbol(name="baz", module_path="/a/c.py", line=5, kind="class"),
    ]
    output = format_dead_code(results)
    assert "3 dead symbol(s)" in output
    assert "foo" in output
    assert "bar" in output
    assert "baz" in output
    assert "/a/b.py" in output
    assert "/a/c.py" in output
