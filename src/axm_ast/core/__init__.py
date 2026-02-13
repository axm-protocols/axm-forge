"""Core parsing and analysis engine.

This module re-exports the main entry points:
- ``parse_file`` / ``extract_module_info`` — tree-sitter parsing
- ``analyze_package`` — high-level package analysis
"""

from axm_ast.core.analyzer import analyze_package
from axm_ast.core.parser import extract_module_info, parse_file

__all__ = ["analyze_package", "extract_module_info", "parse_file"]
