from __future__ import annotations

import ast
import re
import tomllib
from collections.abc import Callable
from pathlib import Path
from typing import cast

from axm_ast import (
    ClassInfo,
    FunctionInfo,
    ModuleInfo,
    PackageInfo,
    analyze_package,
    search_symbols,
)

from axm_init.models.check import CheckResult

__all__ = [
    "check_author_grammar",
    "check_protocol_assembly",
    "check_protocol_components",
    "check_protocols_profile",
    "check_protocols_resources",
]

__axm_explicit_only__ = True

_CATEGORY = "protocols"
_SCHEMA_VERSION = 1
_SEGMENT = re.compile(r"^[a-z][a-z0-9_]*$")


def _table(value: object) -> dict[str, object] | None:
    if not isinstance(value, dict):
        return None
    return cast("dict[str, object]", value)


def _tables(value: object) -> list[dict[str, object]] | None:
    if not isinstance(value, list):
        return None
    tables: list[dict[str, object]] = []
    for item in value:
        table = _table(item)
        if table is None:
            return None
        tables.append(table)
    return tables


def _strings(value: object) -> list[str] | None:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        return None
    return cast("list[str]", value)


def _nested(data: dict[str, object], *keys: str) -> dict[str, object] | None:
    current = data
    for key in keys:
        child = _table(current.get(key))
        if child is None:
            return None
        current = child
    return current


def _line(text: str, needle: str) -> int:
    for number, line in enumerate(text.splitlines(), start=1):
        if needle in line:
            return number
    return 1


def _finding(text: str, needle: str, problem: str, correction: str) -> str:
    return f"pyproject.toml:{_line(text, needle)}: {problem}. Correction: {correction}"


def _invalid_names(
    text: str,
    label: str,
    names: list[str],
    details: list[str],
) -> None:
    for name in names:
        if not _SEGMENT.fullmatch(name):
            details.append(
                _finding(
                    text,
                    f'"{name}"',
                    f"invalid {label} name {name!r}",
                    "use lower_snake_case",
                )
            )


def _duplicates(
    text: str,
    label: str,
    names: list[str],
    details: list[str],
) -> None:
    seen: set[str] = set()
    for name in names:
        if name in seen:
            details.append(
                _finding(
                    text,
                    f'"{name}"',
                    f"duplicate {label} name {name!r}",
                    f"keep exactly one {label} named {name!r}",
                )
            )
        seen.add(name)


def _validate_components(
    text: str,
    protocol: dict[str, object],
    details: list[str],
) -> None:
    for field in ("contracts", "nodes", "prompts", "phases"):
        values = _strings(protocol.get(field))
        if values is None:
            details.append(
                _finding(
                    text,
                    f"{field} =",
                    f"{field} must be a list of names",
                    f"declare {field} as a TOML string array",
                )
            )
            continue
        _invalid_names(text, field[:-1], values, details)
        _duplicates(text, field[:-1], values, details)


def _protocol_inventory(pkg: PackageInfo) -> tuple[set[str], dict[str, set[str]]]:
    symbols: dict[str, set[str]] = {}
    for module_name, symbol in search_symbols(pkg):
        qualified = (
            module_name
            if module_name == pkg.name or module_name.startswith(f"{pkg.name}.")
            else f"{pkg.name}.{module_name}"
        )
        symbols.setdefault(qualified, set()).add(symbol.name)
    return set(symbols), symbols


_COMPONENT_SUFFIXES = {
    "contracts": ".py",
    "nodes": ".py",
    "prompts": ".md",
    "phases": ".py",
}


def _required_action_paths(module_root: Path, action_root: Path) -> tuple[Path, ...]:
    unit_root = action_root.parent
    return (
        module_root / "__init__.py",
        unit_root / "__init__.py",
        action_root / "__init__.py",
        action_root / "protocol.py",
        action_root / "contracts",
        action_root / "contracts" / "__init__.py",
        action_root / "nodes",
        action_root / "nodes" / "__init__.py",
        action_root / "prompts",
        action_root / "prompts" / "__init__.py",
        action_root / "phases",
        action_root / "phases" / "__init__.py",
    )


def _validate_required_paths(
    project: Path,
    text: str,
    paths: tuple[Path, ...],
    details: list[str],
) -> None:
    for path in paths:
        if path.exists():
            continue
        relative = path.relative_to(project).as_posix()
        details.append(
            _finding(
                text,
                "[tool.axm-init.protocols]",
                f"required protocol path {relative} is missing",
                f"create {relative}",
            )
        )


def _local_components(directory: Path, suffix: str) -> set[str]:
    if not directory.is_dir():
        return set()
    return {
        path.stem
        for path in directory.iterdir()
        if path.is_file() and path.suffix == suffix and path.name != "__init__.py"
    }


def _validate_component_inventory(
    project: Path,
    text: str,
    action_root: Path,
    protocol: dict[str, object],
    details: list[str],
) -> None:
    for field, suffix in _COMPONENT_SUFFIXES.items():
        declared_values = _strings(protocol.get(field))
        if declared_values is None:
            continue
        directory = action_root / field
        if not directory.is_dir():
            continue
        declared = set(declared_values)
        local = _local_components(directory, suffix)
        for name in sorted(declared - local):
            relative = (directory / f"{name}{suffix}").relative_to(project).as_posix()
            details.append(
                _finding(
                    text,
                    f"{field} =",
                    f"declared {field[:-1]} {name!r} is missing on disk at {relative}",
                    f"create {relative} or remove {name!r} from the {field} inventory",
                )
            )
        for name in sorted(local - declared):
            relative = (directory / f"{name}{suffix}").relative_to(project).as_posix()
            details.append(
                _finding(
                    text,
                    f"{field} =",
                    f"local {field[:-1]} {name!r} at {relative} is not inventoried",
                    f"add {name!r} to the {field} inventory or remove {relative}",
                )
            )


def _validate_protocol_tree(
    project: Path,
    text: str,
    domain: str,
    units: list[dict[str, object]],
    details: list[str],
) -> None:
    module_name = f"protocols_{domain}"
    module_root = project / "src" / module_name
    if not module_root.is_dir():
        candidates = sorted(
            path.name for path in (project / "src").glob("protocols_*") if path.is_dir()
        )
        found = ", ".join(candidates) or "none"
        details.append(
            _finding(
                text,
                f'domain = "{domain}"',
                f"protocol module mismatch: expected {module_name}, found {found}",
                f"rename the protocol module root to src/{module_name}",
            )
        )
        return

    pkg = analyze_package(module_root)
    modules, _symbols = _protocol_inventory(pkg)
    declared: set[tuple[str, str]] = set()
    for unit in units:
        unit_name = unit.get("name")
        protocols = _tables(unit.get("protocols"))
        if not isinstance(unit_name, str) or protocols is None:
            continue
        for protocol in protocols:
            action = protocol.get("action")
            if not isinstance(action, str):
                continue
            declared.add((unit_name, action))
            action_root = module_root / unit_name / action
            _validate_required_paths(
                project,
                text,
                _required_action_paths(module_root, action_root),
                details,
            )
            _validate_component_inventory(
                project,
                text,
                action_root,
                protocol,
                details,
            )

    for module in sorted(modules):
        if not module.endswith(".protocol"):
            continue
        parts = module.split(".")
        if len(parts) >= 4 and (parts[-3], parts[-2]) not in declared:
            graph_name = ".".join(parts[-3:-1])
            details.append(
                _finding(
                    text,
                    "[[tool.axm-init.protocols.units",
                    f"orphan protocol module {graph_name}",
                    f"declare unit {parts[-3]!r} and action {parts[-2]!r} in metadata",
                )
            )


def _validate_unit_protocols(
    text: str,
    name: str,
    protocols: list[dict[str, object]],
    details: list[str],
) -> None:
    """Validate the protocol tables nested under one declared unit."""
    actions = [
        action
        for protocol in protocols
        if isinstance((action := protocol.get("action")), str)
    ]
    _invalid_names(text, "protocol action", actions, details)
    _duplicates(text, "protocol action", actions, details)
    for protocol in protocols:
        if not isinstance(protocol.get("action"), str):
            details.append(
                _finding(
                    text,
                    "[[tool.axm-init.protocols.units.protocols]]",
                    f"protocol action is missing in unit {name!r}",
                    "add a lower_snake_case action",
                )
            )
        _validate_components(text, protocol, details)


def _unit_protocols_or_finding(
    text: str,
    unit: dict[str, object],
    details: list[str],
) -> tuple[str, list[dict[str, object]]] | None:
    """Return one unit's name and protocol tables, or record why it is invalid."""
    name = unit.get("name")
    if not isinstance(name, str):
        details.append(
            _finding(
                text,
                "[[tool.axm-init.protocols.units]]",
                "unit name is missing",
                "add a lower_snake_case name",
            )
        )
        return None
    protocols = _tables(unit.get("protocols"))
    if protocols is None:
        details.append(
            _finding(
                text,
                f'name = "{name}"',
                f"unit {name!r} has no protocols array",
                "add at least one nested protocols table",
            )
        )
        return None
    return name, protocols


def _validate_units(
    text: str,
    profile: dict[str, object],
    details: list[str],
) -> list[dict[str, object]]:
    units = _tables(profile.get("units"))
    if units is None:
        details.append(
            _finding(
                text,
                "[tool.axm-init.protocols]",
                "units must be an array of tables",
                "add [[tool.axm-init.protocols.units]] declarations",
            )
        )
        return []

    unit_names = [name for unit in units if isinstance((name := unit.get("name")), str)]
    _invalid_names(text, "unit", unit_names, details)
    _duplicates(text, "unit", unit_names, details)
    for unit in units:
        resolved = _unit_protocols_or_finding(text, unit, details)
        if resolved is None:
            continue
        name, protocols = resolved
        _validate_unit_protocols(text, name, protocols, details)
    return units


def _validate_identity(
    data: dict[str, object],
    profile: dict[str, object],
    text: str,
    details: list[str],
) -> str | None:
    domain = profile.get("domain")
    if not isinstance(domain, str) or not _SEGMENT.fullmatch(domain):
        details.append(
            _finding(
                text,
                "domain =",
                f"invalid protocol domain {domain!r}",
                "set domain to a lower_snake_case name",
            )
        )
        return None

    project = _nested(data, "project")
    distribution = project.get("name") if project else None
    # ``protocols-<domain>``, per the specification and per what the scaffold
    # actually emits (the rendered root module is ``protocols_<domain>``). An
    # ``axm-`` prefix here would reject every tree the scaffold produces.
    expected_distribution = f"protocols-{domain.replace('_', '-')}"
    if distribution != expected_distribution:
        details.append(
            _finding(
                text,
                "name =",
                (
                    f"distribution {distribution!r} is incompatible with "
                    f"protocol domain {domain!r}"
                ),
                f'set project.name = "{expected_distribution}"',
            )
        )
    return domain


def _validate_wheel_inclusion(
    data: dict[str, object],
    text: str,
    domain: str,
    details: list[str],
) -> None:
    wheel = _nested(data, "tool", "hatch", "build", "targets", "wheel")
    packages = _strings(wheel.get("packages")) if wheel else None
    expected = f"src/protocols_{domain}"
    if packages is None or expected not in packages:
        details.append(
            _finding(
                text,
                "[tool.hatch.build.targets.wheel]",
                f"protocol resources under {expected} are not included in the wheel",
                f'add "{expected}" to tool.hatch.build.targets.wheel.packages',
            )
        )


def _workspace_member_failures(
    project: Path,
    check: Callable[[Path], CheckResult],
) -> list[tuple[str, str]] | None:
    """Collect per-member findings, or None when the check does not apply."""
    from axm_ingot.uv import resolve_workspace

    workspace = resolve_workspace(project)
    if workspace is None:
        return None

    applicable: list[tuple[str, CheckResult]] = []
    for member in workspace.members:
        result = check(member.path)
        if result.weight:
            applicable.append((member.name, result))
    if not applicable:
        return None

    return [
        (member_name, detail)
        for member_name, result in applicable
        if not result.passed
        for detail in result.details
    ]


def _workspace_result(
    name: str,
    weight: int,
    passed_message: str,
    failed_prefix: str,
    failures: list[tuple[str, str]],
) -> CheckResult:
    """Assemble the aggregated workspace-level result from member findings."""
    passed = not failures
    return CheckResult(
        name=name,
        category=_CATEGORY,
        passed=passed,
        weight=weight,
        message=(
            passed_message if passed else f"{failed_prefix} {len(failures)} finding(s)"
        ),
        details=[f"member {member_name}: {detail}" for member_name, detail in failures],
        fix="" if passed else "Apply each correction in the named workspace member.",
    )


def _workspace_protocol_result(project: Path) -> CheckResult | None:
    failures = _workspace_member_failures(project, check_protocols_profile)
    if failures is None:
        return None
    return _workspace_result(
        "protocols.profile",
        4,
        "Workspace protocol profiles are statically coherent",
        "Workspace protocol profiles have",
        failures,
    )


def _declared_prompt_paths(
    project: Path,
    profile: dict[str, object],
) -> list[Path]:
    domain = profile.get("domain")
    units = _tables(profile.get("units"))
    if not isinstance(domain, str) or units is None:
        return []

    module_root = project / "src" / f"protocols_{domain}"
    paths: list[Path] = []
    for unit in units:
        unit_name = unit.get("name")
        protocols = _tables(unit.get("protocols"))
        if not isinstance(unit_name, str) or protocols is None:
            continue
        for protocol in protocols:
            action = protocol.get("action")
            prompts = _strings(protocol.get("prompts"))
            if not isinstance(action, str) or prompts is None:
                continue
            paths.extend(
                module_root / unit_name / action / "prompts" / f"{prompt}.md"
                for prompt in prompts
            )
    return paths


def _protocol_resources_included(
    data: dict[str, object],
    domain: str,
) -> bool:
    force_include = _nested(
        data,
        "tool",
        "hatch",
        "build",
        "targets",
        "wheel",
        "force-include",
    )
    expected_source = f"src/protocols_{domain}"
    expected_target = f"protocols_{domain}"
    return (
        force_include is not None
        and force_include.get(expected_source) == expected_target
    )


def _workspace_protocol_resources_result(project: Path) -> CheckResult | None:
    failures = _workspace_member_failures(project, check_protocols_resources)
    if failures is None:
        return None
    return _workspace_result(
        "protocols.protocols_resources",
        2,
        "Workspace protocol prompt resources are distributable",
        "Workspace protocol resources have",
        failures,
    )


def _protocol_package(project: Path) -> tuple[str, Path, PackageInfo] | None:
    """Return the explicitly declared protocol package, when applicable."""
    try:
        data = cast(
            "dict[str, object]",
            tomllib.loads((project / "pyproject.toml").read_text(encoding="utf-8")),
        )
    except (OSError, tomllib.TOMLDecodeError):
        return None
    profile = _nested(data, "tool", "axm-init", "protocols")
    domain = profile.get("domain") if profile is not None else None
    if not isinstance(domain, str):
        return None
    root = project / "src" / f"protocols_{domain}"
    if not root.is_dir():
        return None
    return domain, root, analyze_package(root)


def _content_result(name: str, details: list[str], *, applicable: bool) -> CheckResult:
    """Build a consistently weighted static-content result."""
    passed = not details
    if not applicable:
        message = "Protocol profile not declared"
    elif passed:
        message = f"{name} is conforming"
    else:
        message = f"{name} has {len(details)} finding(s)"
    return CheckResult(
        name=name,
        category=_CATEGORY,
        passed=passed,
        weight=2 if applicable else 0,
        message=message,
        details=details,
        fix="" if passed else "Correct each localized static form.",
    )


def _location(project: Path, module: ModuleInfo, line: int) -> str:
    """Render a stable project-relative source location."""
    try:
        relative = module.path.relative_to(project.resolve()).as_posix()
    except ValueError:
        relative = module.path.as_posix()
    return f"{relative}:{line}"


def _principal_kind(module: ModuleInfo) -> str | None:
    """Return the declaration kind implied by a component directory."""
    if module.path.parent.name == "contracts":
        return "class"
    if module.path.parent.name in {"nodes", "phases"}:
        return "function"
    return None


def _principal_candidates(
    module: ModuleInfo, kind: str
) -> list[FunctionInfo | ClassInfo]:
    """Return public declarations independently of explicit exports."""
    if kind == "class":
        return [item for item in module.classes if item.is_public]
    return [item for item in module.functions if item.is_public]


def _component_findings(project: Path, package: PackageInfo) -> list[str]:
    """Validate one explicitly exported principal per component module."""
    details: list[str] = []
    for module in package.modules:
        kind = _principal_kind(module)
        if kind is None or module.path.name == "__init__.py":
            continue
        candidates = _principal_candidates(module, kind)
        if not candidates:
            details.append(
                f"{_location(project, module, 1)}: non-conforming component: "
                "no public principal"
            )
        elif len(candidates) > 1:
            details.append(
                f"{_location(project, module, candidates[1].line_start)}: "
                f"non-conforming component: multiple public principal "
                f"declarations ({len(candidates)})"
            )
        elif module.all_exports is None or candidates[0].name not in module.all_exports:
            details.append(
                f"{_location(project, module, candidates[0].line_start)}: "
                f"non-conforming component: principal {candidates[0].name!r} "
                "is not explicitly exported in __all__"
            )
    return details


def check_protocol_components(project: Path) -> CheckResult:
    """Validate principal components without importing inspected code."""
    context = _protocol_package(project)
    details = [] if context is None else _component_findings(project, context[2])
    return _content_result(
        "protocol_components", details, applicable=context is not None
    )


# Calls are composition only when their local binding resolves to this registry.
_COMPOSITION_INTERFACES = frozenset(
    {
        ("axm_loom", "phase"),
        ("axm_loom", "protocol"),
        ("axm_loom", "router"),
        ("axm_loom", "task"),
    }
)
_SAFE_FACTORY_INTERFACES = _COMPOSITION_INTERFACES | frozenset(
    {
        ("contextvars", "ContextVar"),
        ("logging", "getLogger"),
        ("pydantic", "create_model"),
        ("re", "compile"),
        ("threading", "Lock"),
        ("threading", "RLock"),
    }
)
_SAFE_BUILTINS = frozenset({"dict", "frozenset", "list", "object", "set", "tuple"})


def _import_bindings(module: ModuleInfo) -> dict[str, tuple[str, str]]:
    """Map local names to resolved imports from typed axm-ast results."""
    bindings: dict[str, tuple[str, str]] = {}
    for imported in module.imports:
        if imported.module is None:
            for name in imported.names:
                bindings[imported.alias or name] = (name, "")
        else:
            for name in imported.names:
                bindings[imported.alias or name] = (imported.module, name)
    return bindings


def _resolved_call(
    call: ast.Call, bindings: dict[str, tuple[str, str]]
) -> tuple[str, str] | None:
    """Resolve a call target through typed import bindings."""
    if isinstance(call.func, ast.Name):
        return bindings.get(call.func.id)
    if isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name):
        imported = bindings.get(call.func.value.id)
        if imported is not None:
            return imported[0], call.func.attr
    return None


def _parse(module: ModuleInfo) -> ast.Module:
    """Parse syntax without importing or executing the inspected project."""
    source = module.path.read_text(encoding="utf-8")
    return ast.parse(source, filename=str(module.path))


def _assembly_findings(
    project: Path, domain: str, root: Path, package: PackageInfo
) -> list[str]:
    """Validate the ready assembly factory and its literal graph identity."""
    module = next(
        (item for item in package.modules if item.path.name == "protocol.py"), None
    )
    if module is None:
        return []
    if "# axm-init: incomplete-skeleton" in module.path.read_text(encoding="utf-8"):
        return []
    tree = _parse(module)
    info = next(
        (
            item
            for item in module.functions
            if item.name == "build_protocol" and item.is_public
        ),
        None,
    )
    factory = next(
        (
            node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "build_protocol"
        ),
        None,
    )
    if info is None or factory is None:
        return [
            f"{_location(project, module, 1)}: non-conforming assembly: "
            "expected public factory 'build_protocol' is missing"
        ]
    bindings = _import_bindings(module)
    call = next(
        (
            node
            for node in ast.walk(factory)
            if isinstance(node, ast.Call)
            and _resolved_call(node, bindings) == ("axm_loom", "protocol")
        ),
        None,
    )
    if call is None or not call.args:
        return [
            f"{_location(project, module, info.line_start)}: non-verifiable "
            "assembly: protocol composition call is not statically resolvable"
        ]
    identity = call.args[0]
    if not isinstance(identity, ast.Constant) or not isinstance(identity.value, str):
        return [
            f"{_location(project, module, identity.lineno)}: non-verifiable "
            "assembly: graph name is not a string literal"
        ]
    relative = module.path.relative_to(root)
    expected = ".".join((domain, *relative.parts[:-1]))
    details: list[str] = []
    if identity.value != expected:
        details.append(
            f"{_location(project, module, identity.lineno)}: non-conforming "
            f"assembly: literal graph name {identity.value!r} differs from "
            f"path-derived name {expected!r}"
        )
    return details


def check_protocol_assembly(project: Path) -> CheckResult:
    """Validate assembly factories and graph identities statically."""
    context = _protocol_package(project)
    details = (
        []
        if context is None
        else _assembly_findings(project, context[0], context[1], context[2])
    )
    return _content_result("protocol_assembly", details, applicable=context is not None)


_IO_METHODS = frozenset(
    {
        "mkdir",
        "open",
        "read_bytes",
        "read_text",
        "rename",
        "replace",
        "rmdir",
        "touch",
        "unlink",
        "write_bytes",
        "write_text",
    }
)


def _call_label(call: ast.Call) -> str:
    """Render a bounded syntactic call label."""
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return "call"


def _direct_io(value: ast.AST) -> ast.Call | None:
    """Return the first statically direct filesystem operation."""
    for node in ast.walk(value):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name) and node.func.id == "open":
            return node
        if isinstance(node.func, ast.Attribute) and node.func.attr in _IO_METHODS:
            return node
    return None


def _safe_factory(call: ast.Call, bindings: dict[str, tuple[str, str]]) -> bool:
    """Recognize calibrated declarative factories through imports."""
    if isinstance(call.func, ast.Name) and call.func.id in _SAFE_BUILTINS:
        return True
    return _resolved_call(call, bindings) in _SAFE_FACTORY_INTERFACES


def _assignment_finding(
    project: Path,
    module: ModuleInfo,
    statement: ast.Assign | ast.AnnAssign,
    bindings: dict[str, tuple[str, str]],
) -> str | None:
    """Classify an evaluated module-level assignment."""
    value = statement.value
    if value is None:
        return None
    comprehension = next(
        (
            node
            for node in ast.walk(value)
            if isinstance(
                node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
            )
        ),
        None,
    )
    if comprehension is not None:
        return (
            f"{_location(project, module, comprehension.lineno)}: "
            "non-conforming author form: evaluated module-level comprehension"
        )
    io_call = _direct_io(value)
    if io_call is not None:
        return (
            f"{_location(project, module, io_call.lineno)}: non-conforming "
            f"author form: direct I/O call {_call_label(io_call)!r}"
        )
    if isinstance(value, ast.Call) and not _safe_factory(value, bindings):
        return (
            f"{_location(project, module, value.lineno)}: non-conforming author "
            f"form: observable module-level call {_call_label(value)!r}"
        )
    return None


def _statement_finding(
    project: Path,
    module: ModuleInfo,
    statement: ast.stmt,
    bindings: dict[str, tuple[str, str]],
) -> str | None:
    """Classify one evaluated top-level statement conservatively."""
    if isinstance(statement, (ast.For, ast.AsyncFor, ast.While)):
        return (
            f"{_location(project, module, statement.lineno)}: non-conforming "
            "author form: module-level business iteration"
        )
    if isinstance(statement, (ast.Assign, ast.AnnAssign)):
        return _assignment_finding(project, module, statement, bindings)
    if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call):
        call = statement.value
        io_call = _direct_io(call)
        label = _call_label(io_call or call)
        observed = "direct I/O call" if io_call is not None else "observable call"
        return (
            f"{_location(project, module, call.lineno)}: non-conforming author "
            f"form: module-level {observed} {label!r}"
        )
    return None


def _author_findings(project: Path, package: PackageInfo) -> list[str]:
    """Report evaluated module forms without executing inspected modules."""
    details: list[str] = []
    for module in package.modules:
        if module.path.name == "__init__.py":
            continue
        bindings = _import_bindings(module)
        for statement in _parse(module).body:
            finding = _statement_finding(project, module, statement, bindings)
            if finding is not None:
                details.append(finding)
    return details


def check_author_grammar(project: Path) -> CheckResult:
    """Validate import-time forms through syntax and resolved imports."""
    context = _protocol_package(project)
    details = [] if context is None else _author_findings(project, context[2])
    return _content_result("author_grammar", details, applicable=context is not None)


def _missing_prompt_findings(
    project: Path,
    text: str,
    prompt_paths: list[Path],
) -> list[str]:
    """Report declared prompt resources absent from disk."""
    details: list[str] = []
    for prompt_path in prompt_paths:
        if prompt_path.is_file():
            continue
        relative = prompt_path.relative_to(project).as_posix()
        details.append(
            _finding(
                text,
                "prompts =",
                f"declared prompt resource is missing on disk at {relative}",
                f"create {relative} or remove it from the prompts inventory",
            )
        )
    return details


def _excluded_prompt_findings(
    project: Path,
    text: str,
    data: dict[str, object],
    profile: dict[str, object],
    prompt_paths: list[Path],
) -> list[str]:
    """Report prompt resources left out of the wheel distribution."""
    domain = profile.get("domain")
    if not prompt_paths or not isinstance(domain, str):
        return []
    if _protocol_resources_included(data, domain):
        return []
    source = f"src/protocols_{domain}"
    target = f"protocols_{domain}"
    relative_prompts = ", ".join(
        path.relative_to(project).as_posix() for path in prompt_paths
    )
    return [
        _finding(
            text,
            "[tool.hatch.build.targets.wheel]",
            f"prompt resources {relative_prompts} are excluded from the distribution",
            "declare [tool.hatch.build.targets.wheel.force-include] and add "
            f'"{source}" = "{target}"',
        )
    ]


def check_protocols_resources(project: Path) -> CheckResult:
    """Validate declared prompt files and their distribution configuration."""
    metadata = project / "pyproject.toml"
    try:
        text = metadata.read_text(encoding="utf-8")
        data = cast("dict[str, object]", tomllib.loads(text))
    except (OSError, tomllib.TOMLDecodeError):
        return CheckResult(
            name="protocols.protocols_resources",
            category=_CATEGORY,
            passed=True,
            weight=0,
            message="Protocol prompt resources are not applicable",
            details=[],
            fix="",
        )

    profile = _nested(data, "tool", "axm-init", "protocols")
    if profile is None:
        workspace_result = _workspace_protocol_resources_result(project)
        if workspace_result is not None:
            return workspace_result
        return CheckResult(
            name="protocols.protocols_resources",
            category=_CATEGORY,
            passed=True,
            weight=0,
            message="Protocol profile not declared",
            details=[],
            fix="",
        )

    prompt_paths = _declared_prompt_paths(project, profile)
    details = _missing_prompt_findings(project, text, prompt_paths)
    details.extend(
        _excluded_prompt_findings(project, text, data, profile, prompt_paths)
    )

    passed = not details
    return CheckResult(
        name="protocols.protocols_resources",
        category=_CATEGORY,
        passed=passed,
        weight=2,
        message=(
            "Protocol prompt resources are present and distributable"
            if passed
            else f"Protocol prompt resources have {len(details)} finding(s)"
        ),
        details=details,
        fix="" if passed else "Apply every correction listed in the findings.",
    )


def check_protocols_profile(project: Path) -> CheckResult:
    """Validate a declared protocol profile without importing inspected code."""
    metadata = project / "pyproject.toml"
    try:
        text = metadata.read_text(encoding="utf-8")
        data = cast("dict[str, object]", tomllib.loads(text))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return CheckResult(
            name="protocols.profile",
            category=_CATEGORY,
            passed=False,
            weight=4,
            message="Protocol metadata is unreadable",
            details=[f"pyproject.toml:1: {exc}. Correction: fix the TOML metadata"],
            fix="Fix pyproject.toml before validating the protocol profile.",
        )

    profile = _nested(data, "tool", "axm-init", "protocols")
    if profile is None:
        workspace_result = _workspace_protocol_result(project)
        if workspace_result is not None:
            return workspace_result
        return CheckResult(
            name="protocols.profile",
            category=_CATEGORY,
            passed=True,
            weight=0,
            message="Protocol profile not declared",
            details=[],
            fix="",
        )

    details: list[str] = []
    schema_version = profile.get("schema_version")
    if schema_version != _SCHEMA_VERSION:
        details.append(
            _finding(
                text,
                "schema_version",
                f"unsupported schema_version {schema_version!r}",
                f"set schema_version = {_SCHEMA_VERSION}",
            )
        )

    domain = _validate_identity(data, profile, text, details)
    units = _validate_units(text, profile, details)
    if domain is not None:
        _validate_wheel_inclusion(data, text, domain, details)
        _validate_protocol_tree(project, text, domain, units, details)

    passed = not details
    return CheckResult(
        name="protocols.profile",
        category=_CATEGORY,
        passed=passed,
        weight=4,
        message=(
            "Protocol profile is statically coherent"
            if passed
            else f"Protocol profile has {len(details)} finding(s)"
        ),
        details=details,
        fix="" if passed else "Apply every correction listed in the findings.",
    )
