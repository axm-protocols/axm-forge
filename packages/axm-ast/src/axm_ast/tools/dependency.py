"""AST projection of declared dependency modules using the SDK read resolver."""

from __future__ import annotations

from axm.tools.base import ToolResult
from axm.tools.dependency_reads import session_dependencies

from axm_ast.core.parser import extract_module_info
from axm_ast.models.nodes import PackageInfo

__all__ = ["dependency_package", "inspect_with_dependencies"]


def dependency_package(symbol: str) -> tuple[PackageInfo, str] | None:
    """Parse only the resolved module, never import or index a whole environment."""
    resolved = session_dependencies().resolve_symbol(symbol)
    if resolved is None:
        return None
    path, module, member = resolved
    # PackageInfo.module_names derives qualified names relative to this root.
    parts = module.split(".")
    root = path.parent
    count = len(parts) if path.name == "__init__.py" else len(parts) - 1
    for _ in range(count):
        root = root.parent
    package = PackageInfo(name=parts[0], root=root, modules=[extract_module_info(path)])
    return package, member


def inspect_with_dependencies(
    pkg: PackageInfo, symbol: str, *, source: bool = False
) -> ToolResult:
    """Keep local precedence; resolve missing qualified names in declared sources."""
    from axm_ast.tools.inspect_resolve import inspect_dotted

    result = inspect_dotted(pkg, symbol, source=source)
    if result.success:
        return result
    external = dependency_package(symbol)
    if external is None:
        return result
    if "." in external[1]:
        from axm_ast.tools.inspect_resolve import resolve_class_method

        method = resolve_class_method(external[0], external[1], source=source)
        if method is not None:
            return method
    module = external[0].module_names[0]
    qualified = f"{module}.{external[1]}" if external[1] else module
    return inspect_dotted(external[0], qualified, source=source)
