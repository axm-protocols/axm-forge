"""Core parsing and analysis engine.

This module re-exports the main entry points:
- ``parse_file`` / ``extract_module_info`` — tree-sitter parsing
- ``analyze_package`` — high-level package analysis
- ``get_package`` / ``clear_cache`` — cached package access
"""

from axm_ast.core.analyzer import analyze_package
from axm_ast.core.cache import clear_cache, get_package
from axm_ast.core.parser import extract_module_info, parse_file

__all__ = [
    "analyze_package",
    "clear_cache",
    "extract_module_info",
    "get_package",
    "parse_file",
]
