"""Audit checks for pyproject.toml (9 checks, 27 pts)."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from pathlib import Path

from axm_init.checks._utils import TomlTable, load_toml, requires_toml, section
from axm_init.models.check import CheckResult

logger = logging.getLogger(__name__)


def check_pyproject_exists(project: Path) -> CheckResult:
    """Check 1: pyproject.toml exists and is parsable."""
    path = project / "pyproject.toml"
    if not path.exists():
        return CheckResult(
            name="pyproject.exists",
            category="pyproject",
            passed=False,
            weight=4,
            message="pyproject.toml not found",
            details=[],
            fix="Create a pyproject.toml at the project root.",
        )
    data = load_toml(project)
    if data is None:
        return CheckResult(
            name="pyproject.exists",
            category="pyproject",
            passed=False,
            weight=4,
            message="pyproject.toml is unparsable",
            details=["File exists but contains invalid TOML"],
            fix="Fix TOML syntax errors in pyproject.toml.",
        )
    return CheckResult(
        name="pyproject.exists",
        category="pyproject",
        passed=True,
        weight=4,
        message="pyproject.toml found",
        details=[],
        fix="",
    )


@requires_toml(
    check_name="pyproject.urls",
    category="pyproject",
    weight=3,
    fix="Create pyproject.toml with [project.urls] section.",
)
def check_pyproject_urls(project: Path, data: TomlTable) -> CheckResult:
    """Check 2: [project.urls] with 4 keys."""
    required = {"Homepage", "Documentation", "Repository", "Issues"}
    urls = section(section(data, "project"), "urls")
    present = set(urls.keys()) & required
    missing = required - present
    if missing:
        return CheckResult(
            name="pyproject.urls",
            category="pyproject",
            passed=False,
            weight=3,
            message=f"Missing {len(missing)} URL(s) in [project.urls]",
            details=[
                f"Missing: {', '.join(sorted(missing))}",
                f"Present: {', '.join(sorted(present))}",
            ],
            fix=(
                f"Add {', '.join(sorted(missing))} to [project.urls] in pyproject.toml."
            ),
        )
    return CheckResult(
        name="pyproject.urls",
        category="pyproject",
        passed=True,
        weight=3,
        message="All 4 URLs present",
        details=[],
        fix="",
    )


@requires_toml(
    check_name="pyproject.dynamic_version",
    category="pyproject",
    weight=3,
    fix="Create pyproject.toml with dynamic version using hatch-vcs.",
)
def check_pyproject_dynamic_version(project: Path, data: TomlTable) -> CheckResult:
    """Check 3: dynamic = ['version'] + hatch-vcs."""
    dynamic_raw = section(data, "project").get("dynamic", [])
    requires_raw = section(data, "build-system").get("requires", [])
    dynamic = dynamic_raw if isinstance(dynamic_raw, list) else []
    requires = requires_raw if isinstance(requires_raw, list) else []
    has_dynamic = "version" in dynamic
    has_hatch_vcs = any(isinstance(r, str) and "hatch-vcs" in r for r in requires)
    problems = []
    if not has_dynamic:
        problems.append('Missing: dynamic = ["version"]')
    if not has_hatch_vcs:
        problems.append("Missing: hatch-vcs in build-system.requires")
    if problems:
        return CheckResult(
            name="pyproject.dynamic_version",
            category="pyproject",
            passed=False,
            weight=3,
            message="Version is not dynamically managed",
            details=problems,
            fix='Add hatch-vcs to build-system.requires and set dynamic = ["version"].',
        )
    return CheckResult(
        name="pyproject.dynamic_version",
        category="pyproject",
        passed=True,
        weight=3,
        message="Dynamic version with hatch-vcs",
        details=[],
        fix="",
    )


STRICT_IMPLIES = {"disallow_incomplete_defs", "check_untyped_defs"}


def _filter_strict_implied(missing: list[str], mypy: TomlTable) -> list[str]:
    """Remove keys implied by strict=True unless explicitly set to False."""
    if mypy.get("strict") is not True:
        return missing
    return [k for k in missing if k not in STRICT_IMPLIES or mypy.get(k) is False]


@requires_toml(
    check_name="pyproject.mypy",
    category="pyproject",
    weight=3,
    fix="Create pyproject.toml with [tool.mypy] section.",
)
def check_pyproject_mypy(project: Path, data: TomlTable) -> CheckResult:
    """Check 4: strict + pretty + disallow_incomplete_defs + check_untyped_defs."""
    mypy = section(section(data, "tool"), "mypy")
    required = {
        "strict": True,
        "pretty": True,
        "disallow_incomplete_defs": True,
        "check_untyped_defs": True,
    }
    missing = [k for k, v in required.items() if mypy.get(k) != v]
    missing = _filter_strict_implied(missing, mypy)
    present = [k for k in required if k not in missing]
    if missing:
        return CheckResult(
            name="pyproject.mypy",
            category="pyproject",
            passed=False,
            weight=3,
            message=f"MyPy config incomplete — missing {len(missing)} setting(s)",
            details=[
                f"Missing: {', '.join(missing)}",
                f"Present: {', '.join(present)}",
            ],
            fix=f"Add {', '.join(f'{k} = true' for k in missing)} to [tool.mypy].",
        )
    return CheckResult(
        name="pyproject.mypy",
        category="pyproject",
        passed=True,
        weight=3,
        message="MyPy fully configured",
        details=[],
        fix="",
    )


@requires_toml(
    check_name="pyproject.ruff",
    category="pyproject",
    weight=3,
    fix="Create pyproject.toml with [tool.ruff.lint] section.",
)
def check_pyproject_ruff(project: Path, data: TomlTable) -> CheckResult:
    """Check 5: per-file-ignores + known-first-party."""
    ruff_lint = section(section(section(data, "tool"), "ruff"), "lint")
    problems = []
    if "per-file-ignores" not in ruff_lint:
        problems.append("Missing: [tool.ruff.lint.per-file-ignores]")
    isort = section(ruff_lint, "isort")
    if "known-first-party" not in isort:
        problems.append("Missing: known-first-party in [tool.ruff.lint.isort]")
    if problems:
        return CheckResult(
            name="pyproject.ruff",
            category="pyproject",
            passed=False,
            weight=3,
            message="Ruff config incomplete",
            details=problems,
            fix="Add per-file-ignores for tests and known-first-party to ruff config.",
        )
    return CheckResult(
        name="pyproject.ruff",
        category="pyproject",
        passed=True,
        weight=3,
        message="Ruff fully configured",
        details=[],
        fix="",
    )


@requires_toml(
    check_name="pyproject.pytest",
    category="pyproject",
    weight=4,
    fix="Create pyproject.toml with [tool.pytest.ini_options].",
)
def check_pyproject_pytest(project: Path, data: TomlTable) -> CheckResult:
    """Check 6: pytest config completeness."""
    pytest_cfg = section(section(section(data, "tool"), "pytest"), "ini_options")
    addopts_raw = pytest_cfg.get("addopts", [])
    addopts_list = addopts_raw if isinstance(addopts_raw, list) else []
    addopts = " ".join(str(a) for a in addopts_list)
    problems = []
    if "--strict-markers" not in addopts:
        problems.append("Missing: --strict-markers in addopts")
    if "--strict-config" not in addopts:
        problems.append("Missing: --strict-config in addopts")
    if "--import-mode=importlib" not in addopts:
        problems.append("Missing: --import-mode=importlib in addopts")
    if "pythonpath" not in pytest_cfg:
        problems.append('Missing: pythonpath = ["src"]')
    if "filterwarnings" not in pytest_cfg:
        problems.append("Missing: filterwarnings")
    if problems:
        return CheckResult(
            name="pyproject.pytest",
            category="pyproject",
            passed=False,
            weight=4,
            message=f"Pytest config incomplete — missing {len(problems)} setting(s)",
            details=problems,
            fix="Add missing settings to [tool.pytest.ini_options].",
        )
    return CheckResult(
        name="pyproject.pytest",
        category="pyproject",
        passed=True,
        weight=4,
        message="Pytest fully configured",
        details=[],
        fix="",
    )


@requires_toml(
    check_name="pyproject.coverage",
    category="pyproject",
    weight=4,
    fix="Create pyproject.toml with [tool.coverage] sections.",
)
def check_pyproject_coverage(project: Path, data: TomlTable) -> CheckResult:
    """Check 7: branch, relative_files, xml output, exclude_lines."""
    cov = section(section(data, "tool"), "coverage")
    run_cfg = section(cov, "run")
    problems = []
    if not run_cfg.get("branch"):
        problems.append("Missing: branch = true in [tool.coverage.run]")
    if not run_cfg.get("relative_files"):
        problems.append("Missing: relative_files = true in [tool.coverage.run]")
    if "xml" not in cov:
        problems.append("Missing: [tool.coverage.xml] section")
    if "exclude_lines" not in section(cov, "report"):
        problems.append("Missing: exclude_lines in [tool.coverage.report]")
    if problems:
        return CheckResult(
            name="pyproject.coverage",
            category="pyproject",
            passed=False,
            weight=4,
            message=f"Coverage config incomplete — missing {len(problems)} setting(s)",
            details=problems,
            fix="Add missing settings to [tool.coverage] sections.",
        )
    return CheckResult(
        name="pyproject.coverage",
        category="pyproject",
        passed=True,
        weight=4,
        message="Coverage fully configured",
        details=[],
        fix="",
    )


def _derive_package_import_path(data: TomlTable) -> str:
    """Derive the wheel import path from ``[tool.hatch.build.targets.wheel].packages``.

    Returns the first ``packages`` entry stripped of any ``src/`` prefix
    (e.g. ``["src/axm_audit"]`` -> ``"axm_audit"``). Falls back to the
    ``[project].name`` with hyphens converted to underscores, then to
    ``"pkg"`` if neither is available.
    """
    wheel_cfg = section(
        section(section(section(data, "tool"), "hatch"), "build"), "targets"
    )
    wheel_section = section(wheel_cfg, "wheel")
    packages_raw = wheel_section.get("packages", [])
    if isinstance(packages_raw, list):
        for entry in packages_raw:
            if isinstance(entry, str) and entry:
                stripped = entry.removeprefix("src/").removeprefix("./")
                if stripped:
                    return stripped.split("/")[-1]
    project_name = section(data, "project").get("name", "")
    if isinstance(project_name, str) and project_name:
        return project_name.replace("-", "_")
    return "pkg"


def _expected_doc_files(project: Path, data: TomlTable) -> tuple[list[str], bool]:
    """Return ``(doc_files, is_explicit)``.

    Resolution order: explicit ``[tool.axm-init.wheel-doc].files`` list
    wins; otherwise auto-detect ``docs/*.md`` from disk. An empty list
    with no ``docs/`` dir means "no docs to ship" and the check passes.
    """
    wheel_doc_section = section(section(data, "tool"), "axm-init").get("wheel-doc")
    if isinstance(wheel_doc_section, Mapping):
        files_raw = wheel_doc_section.get("files", [])
        if isinstance(files_raw, list):
            return [f for f in files_raw if isinstance(f, str)], True
        return [], True
    docs_dir = project / "docs"
    if not docs_dir.is_dir():
        return [], False
    discovered = sorted(f"docs/{p.name}" for p in docs_dir.glob("*.md") if p.is_file())
    return discovered, False


@requires_toml(
    check_name="pyproject.wheel_doc_shipping",
    category="pyproject",
    weight=2,
    fix="Add pyproject.toml to enable wheel-doc shipping checks.",
)
def check_pyproject_wheel_doc_shipping(project: Path, data: TomlTable) -> CheckResult:
    """Check 38: docs declared for shipping appear in wheel force-include.

    Verifies that markdown docs intended to ship inside the wheel are
    explicitly wired through
    ``[tool.hatch.build.targets.wheel.force-include]``. Without this
    wiring, ``hatchling`` excludes them from the built wheel and they
    are silently missing from the published distribution.

    Resolution order:
      1. Explicit ``[tool.axm-init.wheel-doc].files`` list (opt-in).
      2. Auto-detect ``docs/*.md`` on disk (WARNING-level failure when
         present but not force-included).
      3. No docs anywhere -> pass silently.
    """
    doc_files, is_explicit = _expected_doc_files(project, data)
    if not doc_files:
        return CheckResult(
            name="pyproject.wheel_doc_shipping",
            category="pyproject",
            passed=True,
            weight=2,
            message="No wheel-doc files declared or discovered",
            details=[],
            fix="",
        )
    wheel_cfg = section(
        section(section(section(data, "tool"), "hatch"), "build"), "targets"
    )
    force_include = section(section(wheel_cfg, "wheel"), "force-include")
    missing = [f for f in doc_files if f not in force_include]
    if not missing:
        return CheckResult(
            name="pyproject.wheel_doc_shipping",
            category="pyproject",
            passed=True,
            weight=2,
            message=f"All {len(doc_files)} wheel-doc file(s) force-included",
            details=[],
            fix="",
        )
    import_path = _derive_package_import_path(data)
    snippet_lines = ["[tool.hatch.build.targets.wheel.force-include]"]
    for f in missing:
        snippet_lines.append(f'"{f}" = "{import_path}/{f}"')
    snippet = "\n".join(snippet_lines)
    if is_explicit:
        message = (
            f"{len(missing)} declared wheel-doc file(s) missing from force-include"
        )
        fix = f"Add to pyproject.toml:\n{snippet}"
    else:
        message = f"{len(missing)} auto-detected docs/*.md file(s) not force-included"
        fix = (
            "Either opt in by force-including the files:\n"
            f"{snippet}\n"
            "or opt out by adding `[tool.axm-init.wheel-doc]` with `files = []`."
        )
    return CheckResult(
        name="pyproject.wheel_doc_shipping",
        category="pyproject",
        passed=False,
        weight=2,
        message=message,
        details=missing,
        fix=fix,
    )


@requires_toml(
    check_name="pyproject.classifiers",
    category="pyproject",
    weight=1,
    fix="Add classifiers to [project] in pyproject.toml.",
)
def check_pyproject_classifiers(project: Path, data: TomlTable) -> CheckResult:
    """Check 36: required classifiers (Dev Status, Python, Typed)."""
    classifiers_raw = section(data, "project").get("classifiers", [])
    classifiers: list[str] = (
        [c for c in classifiers_raw if isinstance(c, str)]
        if isinstance(classifiers_raw, list)
        else []
    )
    required_prefixes = {
        "Development Status": "Development Status ::",
        "Python version": "Programming Language :: Python :: 3",
        "Typed": "Typing :: Typed",
    }
    missing = [
        label
        for label, prefix in required_prefixes.items()
        if not any(c.startswith(prefix) for c in classifiers)
    ]
    if missing:
        return CheckResult(
            name="pyproject.classifiers",
            category="pyproject",
            passed=False,
            weight=1,
            message=f"Missing {len(missing)} required classifier(s)",
            details=[f"Missing: {', '.join(missing)}"],
            fix=(
                "Add Development Status, Python version,"
                " and Typing :: Typed classifiers."
            ),
        )
    return CheckResult(
        name="pyproject.classifiers",
        category="pyproject",
        passed=True,
        weight=1,
        message="Required classifiers present",
        details=[],
        fix="",
    )


@requires_toml(
    check_name="pyproject.ruff_rules",
    category="pyproject",
    weight=2,
    fix="Add [tool.ruff.lint] select with E, F, I, UP, B, S, BLE, PLR, N.",
)
def check_pyproject_ruff_rules(project: Path, data: TomlTable) -> CheckResult:
    """Check 37: essential ruff rule codes activated."""
    ruff_lint = section(section(section(data, "tool"), "ruff"), "lint")
    select_raw = ruff_lint.get("select", [])
    extend_raw = ruff_lint.get("extend-select", [])
    select: set[str] = (
        {s for s in select_raw if isinstance(s, str)}
        if isinstance(select_raw, list)
        else set()
    )
    extend: set[str] = (
        {s for s in extend_raw if isinstance(s, str)}
        if isinstance(extend_raw, list)
        else set()
    )
    all_rules = select | extend
    required = {"E", "F", "I", "UP", "B", "S", "BLE", "PLR", "N"}
    # "ALL" includes everything
    if "ALL" in all_rules:
        missing: set[str] = set()
    else:
        missing = required - all_rules
    if missing:
        return CheckResult(
            name="pyproject.ruff_rules",
            category="pyproject",
            passed=False,
            weight=2,
            message=f"Missing {len(missing)} essential ruff rule(s)",
            details=[f"Missing: {', '.join(sorted(missing))}"],
            fix=f"Add {', '.join(sorted(missing))} to [tool.ruff.lint] select.",
        )
    return CheckResult(
        name="pyproject.ruff_rules",
        category="pyproject",
        passed=True,
        weight=2,
        message="Essential ruff rules activated",
        details=[],
        fix="",
    )
