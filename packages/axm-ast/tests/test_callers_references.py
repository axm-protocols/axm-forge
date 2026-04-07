from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

import pytest

from axm_ast.core.callers import extract_references


@pytest.fixture()
def mod_factory(tmp_path: Path) -> Callable[[str], SimpleNamespace]:
    """Return a factory that writes source to a temp file.

    Returns a ModuleInfo-like object.
    """

    def _make(source: str) -> SimpleNamespace:
        p = tmp_path / "module.py"
        p.write_text(source, encoding="utf-8")
        return SimpleNamespace(path=p)

    return _make


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


def test_positional_arg_class_not_dead(mod_factory):
    """A class passed as a positional arg should appear in refs."""
    source = """
class Handler:
    pass

Server(addr, Handler)
"""
    refs = extract_references(mod_factory(source))
    assert "Handler" in refs


def test_positional_arg_function_not_dead(mod_factory):
    """A function passed as a positional arg should appear in refs."""
    source = """
def transform():
    pass

map(transform, data)
"""
    refs = extract_references(mod_factory(source))
    assert "transform" in refs


def test_positional_arg_literal_not_ref(mod_factory):
    """Literals and calls in argument_list must NOT produce spurious refs."""
    source = """
def baz():
    pass

foo(42, "str", bar())
"""
    refs = extract_references(mod_factory(source))
    # 42, "str" are literals — not refs
    # bar() is a call — tracked by find_callers, not here
    # baz is defined but never referenced
    assert "baz" not in refs
    assert "bar" not in refs
    assert "42" not in refs


def test_positional_arg_attribute_not_dead(mod_factory):
    """An attribute (obj.method) passed as a positional arg should appear in refs."""
    source = """
register(obj.method)
"""
    refs = extract_references(mod_factory(source))
    assert "method" in refs


# ---------------------------------------------------------------------------
# Functional tests
# ---------------------------------------------------------------------------


def test_http_handler_pattern(mod_factory):
    """Realistic HTTPServer pattern — handler class must not be flagged."""
    source = """
from http.server import BaseHTTPRequestHandler, HTTPServer

class MyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

def run():
    server = HTTPServer(("localhost", 8080), MyHandler)
    server.serve_forever()
"""
    refs = extract_references(mod_factory(source))
    assert "MyHandler" in refs


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_nested_call_in_arg(mod_factory):
    """foo(bar()) — bar is a call, not in refs.

    Handled by find_callers.
    """
    source = """
foo(bar())
"""
    refs = extract_references(mod_factory(source))
    assert "bar" not in refs


def test_star_args_not_ref(mod_factory):
    """foo(*handlers) — star-unpacked name is list_splat, should be skipped."""
    source = """
foo(*handlers)
"""
    refs = extract_references(mod_factory(source))
    assert "handlers" not in refs


def test_multiple_positional_args(mod_factory):
    """Server(host, port, Handler, logger) — only identifiers added as refs."""
    source = """
Server(host, port, Handler, logger)
"""
    refs = extract_references(mod_factory(source))
    assert "Handler" in refs
    assert "logger" in refs
    assert "host" in refs
    assert "port" in refs
