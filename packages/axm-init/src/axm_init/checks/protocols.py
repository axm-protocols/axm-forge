from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import cast

from axm_ast import PackageInfo, analyze_package, search_symbols

from axm_init.models.check import CheckResult

__all__ = ["check_protocols_profile"]

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
            prefix = f"{module_name}.{unit_name}.{action}"
            protocol_module = f"{prefix}.protocol"
            if protocol_module not in modules:
                details.append(
                    _finding(
                        text,
                        f'action = "{action}"',
                        f"protocol {unit_name}.{action} has no {protocol_module}.py",
                        f"create src/{protocol_module.replace('.', '/')}.py",
                    )
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
            continue
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
            continue
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
    expected_distribution = f"axm-{domain.replace('_', '-')}"
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
