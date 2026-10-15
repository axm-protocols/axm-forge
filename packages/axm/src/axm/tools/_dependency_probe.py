"""Isolated metadata probe; never import the dependency whose code is being read."""

from __future__ import annotations

import json
import sys
import tomllib
from importlib import metadata
from pathlib import Path
from urllib.parse import unquote, urlparse

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

__all__: list[str] = []


def source_roots(dist: metadata.Distribution) -> list[tuple[str, str]]:
    """Find this distribution's own import roots, including editable installs."""
    direct = dist.read_text("direct_url.json")
    if direct:
        info = json.loads(direct)
        if info.get("dir_info", {}).get("editable"):
            root = Path(unquote(urlparse(info["url"]).path))
            config = tomllib.loads((root / "pyproject.toml").read_text())
            packages = (
                config.get("tool", {})
                .get("hatch", {})
                .get("build", {})
                .get("targets", {})
                .get("wheel", {})
                .get("packages", [])
            )
            if packages:
                return [(Path(p).name, str((root / p).resolve())) for p in packages]
            src = root / "src" if (root / "src").is_dir() else root
            return [
                (p.name, str(p.resolve()))
                for p in src.iterdir()
                if p.is_dir() and (p / "__init__.py").is_file()
            ]
    entries = [
        (Path(str(f)), Path(str(dist.locate_file(f))).resolve())
        for f in (dist.files or ())
        if str(f).endswith(".py") and ".." not in Path(str(f)).parts
    ]
    packages = sorted(
        {
            (relative.parent, absolute.parent)
            for relative, absolute in entries
            if relative.name == "__init__.py"
        },
        key=lambda pair: len(pair[0].parts),
    )
    roots: list[tuple[Path, Path]] = []
    for relative, absolute in packages:
        if not any(relative.is_relative_to(parent) for parent, _ in roots):
            roots.append((relative, absolute))
    result = [(".".join(relative.parts), str(absolute)) for relative, absolute in roots]
    result.extend(
        (".".join(relative.with_suffix("").parts), str(absolute))
        for relative, absolute in entries
        if not any(relative.is_relative_to(parent) for parent, _ in roots)
    )
    return result


def closure(requirements: list[str]) -> list[metadata.Distribution]:
    """Resolve active transitive requirements, retaining extras on every edge."""
    pending = [(r, "") for r in requirements]
    visited: set[tuple[str, tuple[str, ...]]] = set()
    found: dict[str, metadata.Distribution] = {}
    while pending:
        text, parent_extra = pending.pop()
        req = Requirement(text)
        if req.marker and not req.marker.evaluate({"extra": parent_extra}):
            continue
        key = canonicalize_name(req.name), tuple(sorted(req.extras))
        if key in visited:
            continue
        visited.add(key)
        dist = metadata.distribution(req.name)
        found[key[0]] = dist
        for extra in ("", *req.extras):
            pending.extend((child, extra) for child in (dist.requires or ()))
    return list(found.values())


def declared_requirements(config: dict[str, object]) -> list[str]:
    """Include runtime and declared test/dev dependencies, excluding docs."""
    project = config.get("project", {})
    assert isinstance(project, dict)
    requirements = list(project.get("dependencies", []))
    groups = config.get("dependency-groups", {})
    assert isinstance(groups, dict)

    def expand(name: str, stack: tuple[str, ...] = ()) -> list[str]:
        if name in stack:
            raise ValueError(f"cyclic dependency group: {name}")
        entries = groups.get(name, [])
        assert isinstance(entries, list)
        found = []
        for entry in entries:
            if isinstance(entry, str):
                found.append(entry)
            elif isinstance(entry, dict) and isinstance(
                entry.get("include-group"), str
            ):
                found.extend(expand(entry["include-group"], (*stack, name)))
        return found

    for name in ("dev", "test", "tests"):
        requirements.extend(expand(name))
    return requirements


def main() -> None:
    """Project resolved roots using the test runner's ordered import paths."""
    inputs = json.load(sys.stdin)
    sys.path[:0] = inputs["pythonpath"]
    config = tomllib.loads(
        (Path(inputs["package_root"]) / "pyproject.toml").read_text()
    )
    roots = [
        pair
        for dist in closure(declared_requirements(config))
        for pair in source_roots(dist)
    ]
    resolved = []
    for name, root in roots:
        # Test runner pythonpath overrides editable distribution locations.
        alternatives = [
            Path(p).joinpath(*name.split(".")) for p in inputs["pythonpath"]
        ]
        chosen = next(
            (p for p in alternatives if p.is_dir() and (p / "__init__.py").is_file()),
            Path(root),
        )
        resolved.append((name, str(chosen.resolve())))
    sys.stdout.write(json.dumps(sorted(set(resolved))))


if __name__ == "__main__":
    main()
