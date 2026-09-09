"""Integration contracts for static protocol content validation."""

# ruff: noqa: E501
from __future__ import annotations

from pathlib import Path

import pytest

from axm_init.checks.protocols import check_protocols_profile
from axm_init.core.checker import CheckEngine
from tests_axm_init.conftest import (
    materialize_post_copy_artifacts,
    scaffold_without_tasks,
)

pytestmark = pytest.mark.integration

_CONTENT_CHECKS = {
    "protocols.protocol_components",
    "protocols.protocol_assembly",
    "protocols.author_grammar",
}

_PYPROJECT = """[project]
name = "protocols-demo"

[tool.hatch.build.targets.wheel]
packages = ["src/protocols_demo"]

[tool.axm-init.protocols]
schema_version = 1
domain = "demo"

[[tool.axm-init.protocols.units]]
name = "work"

[[tool.axm-init.protocols.units.protocols]]
action = "exec"
contracts = ["request"]
nodes = ["build"]
prompts = []
phases = ["build"]
"""

_READY_FILES = {
    "src/protocols_demo/__init__.py": "",
    "src/protocols_demo/work/__init__.py": "",
    "src/protocols_demo/work/exec/__init__.py": "",
    "src/protocols_demo/work/exec/contracts/__init__.py": "",
    "src/protocols_demo/work/exec/contracts/request.py": """from __future__ import annotations

from pydantic import BaseModel

__all__ = ["Request"]


class _Projection(BaseModel):
    value: str


class Request(BaseModel):
    value: str
""",
    "src/protocols_demo/work/exec/nodes/__init__.py": "",
    "src/protocols_demo/work/exec/nodes/build.py": """from __future__ import annotations

import contextvars
import logging
import re
import threading
from typing import TYPE_CHECKING

from axm_loom import task
from pydantic import create_model

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["PROMPT", "build_node"]

PROMPT = "p" * 1201
_PATTERN = re.compile(r"[a-z]+")
_LOGGER = logging.getLogger(__name__)
_LOCK = threading.Lock()
_CONTEXT = contextvars.ContextVar("context", default=None)
_PrivateModel = create_model("_PrivateModel", value=(str, ...))
_ALIAS = _PATTERN
_DATA = {"kind": "build"}


def _decorator(cls: type[object]) -> type[object]:
    return cls


@_decorator
class _Decorated:
    pass


def _normalize(values: list[str]) -> list[str]:
    normalized: list[str] = []
    for value in values:
        normalized.append(value.strip())
    return normalized


def build_node():
    options: Mapping[str, object] = {"prompt": PROMPT}
    return task("build", prompt=options["prompt"])
""",
    "src/protocols_demo/work/exec/prompts/__init__.py": "",
    "src/protocols_demo/work/exec/phases/__init__.py": "",
    "src/protocols_demo/work/exec/phases/build.py": """from __future__ import annotations

from axm_loom import phase

from ..nodes.build import build_node

__all__ = ["build_phase"]


def build_phase():
    nodes = [build_node()]
    return phase("build", tasks=nodes)
""",
    "src/protocols_demo/work/exec/protocol.py": """from __future__ import annotations

from axm_loom import protocol

from .phases.build import build_phase

__all__ = ["build_protocol"]


def build_protocol():
    phases = [build_phase()]
    options = {"phases": phases}
    return protocol("demo.work.exec", **options)
""",
}


def _project(
    root: Path,
    *,
    replacements: dict[str, str] | None = None,
    profiled: bool = True,
) -> Path:
    root.mkdir(parents=True)
    files = dict(_READY_FILES)
    files.update(replacements or {})
    metadata = _PYPROJECT if profiled else '[project]\nname = "protocols-demo"\n'
    (root / "pyproject.toml").write_text(metadata, encoding="utf-8")
    for relative, source in files.items():
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(source, encoding="utf-8")
    with scaffold_without_tasks():
        materialize_post_copy_artifacts(root)
    return root


def _details(project: Path) -> str:
    profile = check_protocols_profile(project)
    category = _category(project)
    details = [*profile.details]
    details.extend(detail for check in category.checks for detail in check.details)
    return "\n".join(details).lower()


def _category(project: Path):
    return CheckEngine(project, category="protocols").run()


def test_rejects_missing_ambiguous_and_unexported_principals(tmp_path: Path) -> None:
    """AC1: each invalid principal component is localized independently."""
    cases = {
        "missing": {
            "src/protocols_demo/work/exec/phases/build.py": (
                "from __future__ import annotations\n\n_PRIVATE = object()\n"
            )
        },
        "multiple": {
            "src/protocols_demo/work/exec/contracts/request.py": (
                "from __future__ import annotations\n\n"
                '__all__ = ["First", "Second"]\n\n'
                "class First:\n    pass\n\nclass Second:\n    pass\n"
            )
        },
        "unexported": {
            "src/protocols_demo/work/exec/nodes/build.py": (
                "from __future__ import annotations\n\n"
                "__all__: list[str] = []\n\ndef build_node():\n    return None\n"
            )
        },
    }

    observed = {
        label: _details(_project(tmp_path / label, replacements=replacement))
        for label, replacement in cases.items()
    }

    assert (
        "principal" in observed["missing"] and "phases/build.py:" in observed["missing"]
    )
    assert (
        "principal" in observed["multiple"]
        and "contracts/request.py:" in observed["multiple"]
    )
    assert (
        "__all__" in observed["unexported"]
        and "nodes/build.py:" in observed["unexported"]
    )


def test_validates_assembly_factory_and_literal_graph_identity(tmp_path: Path) -> None:
    """AC2: factory absence and path/name disagreement are distinct findings."""
    missing = _project(
        tmp_path / "missing",
        replacements={
            "src/protocols_demo/work/exec/protocol.py": (
                'from __future__ import annotations\n\nGRAPH_NAME = "demo.work.exec"\n'
            )
        },
    )
    mismatch = _project(
        tmp_path / "mismatch",
        replacements={
            "src/protocols_demo/work/exec/protocol.py": (
                _READY_FILES["src/protocols_demo/work/exec/protocol.py"].replace(
                    '"demo.work.exec"', '"demo.work.wrong"'
                )
            )
        },
    )

    missing_details = _details(missing)
    mismatch_details = _details(mismatch)

    assert "factory" in missing_details and "protocol.py:" in missing_details
    assert "graph name" in mismatch_details and "protocol.py:" in mismatch_details
    assert missing_details != mismatch_details


def test_rejects_observable_import_time_execution_structurally(tmp_path: Path) -> None:
    """AC3: module-level iteration, comprehension and I/O are non-conforming.

    Each form asserts its OWN motif, not merely that some finding mentions
    "non-conform": the witness carries other deliberate defects, so a coarse
    substring test stays green even when a whole rule branch is removed
    (measured — deleting the module-level-iteration branch failed none of the
    nine tests in this module).
    """
    forms = {
        "iteration": "for item in ITEMS:\n    consume(item)",
        "comprehension": "VALUES = [consume(item) for item in ITEMS]",
        "direct-io": 'DATA = open("input.txt").read()',
        "external-effect": 'Path("sentinel").write_text("created")',
    }
    # The motif each form must produce, so that removing one branch of the
    # grammar turns exactly one of these red.
    motifs = {
        "iteration": "module-level business iteration",
        "comprehension": "evaluated module-level comprehension",
        "direct-io": "direct i/o call",
        "external-effect": "direct i/o call",
    }
    details: dict[str, str] = {}
    for label, form in forms.items():
        source = (
            "from __future__ import annotations\n"
            "from pathlib import Path\n"
            "from axm_loom import task\n\n"
            '__all__ = ["build_node"]\n'
            "ITEMS = [1]\n"
            "def consume(value):\n    return value\n\n"
            f"{form}\n\n"
            "def build_node():\n    return task('build', prompt='ok')\n"
        )
        project = _project(
            tmp_path / label,
            replacements={"src/protocols_demo/work/exec/nodes/build.py": source},
        )
        details[label] = _details(project)

    assert all("nodes/build.py:" in value for value in details.values())
    for label, motif in motifs.items():
        assert motif in details[label], (
            f"{label}: expected the {motif!r} motif, got {details[label]!r}"
        )


def test_accepts_calibrated_protocol_author_grammar(tmp_path: Path) -> None:
    """AC4: all content checks accept the calibrated ready author forms."""
    project = _project(tmp_path / "ready")
    result = _category(project)
    checks = {check.name: check for check in result.checks}

    assert _CONTENT_CHECKS <= checks.keys()
    assert all(checks[name].passed for name in _CONTENT_CHECKS)
    assert all(
        "non-conform" not in detail.lower() and "non-verifiable" not in detail.lower()
        for name in _CONTENT_CHECKS
        for detail in checks[name].details
    )


def test_reports_unsupported_static_grammar_as_non_verifiable(tmp_path: Path) -> None:
    """AC5: unsupported assembly syntax is localized but never conforming."""
    source = (
        _READY_FILES["src/protocols_demo/work/exec/protocol.py"]
        .replace(
            'protocol("demo.work.exec", **options)',
            "protocol(_graph_name(), **options)",
        )
        .replace(
            "def build_protocol():",
            'def _graph_name():\n    return "demo.work.exec"\n\n\ndef build_protocol():',
        )
    )
    project = _project(
        tmp_path / "unsupported",
        replacements={"src/protocols_demo/work/exec/protocol.py": source},
    )
    result = _category(project)
    assembly = {check.name: check for check in result.checks}[
        "protocols.protocol_assembly"
    ]
    rendered = "\n".join(assembly.details).lower()

    assert not assembly.passed
    assert "non-verifiable" in rendered
    assert "protocol.py:" in rendered
    assert "non-conform" not in rendered


def test_resolves_composition_only_through_import_bindings(tmp_path: Path) -> None:
    """AC6: imports drive composition analysis; textual and homonym decoys do not."""
    source = (
        _READY_FILES["src/protocols_demo/work/exec/nodes/build.py"]
        .replace(
            "from axm_loom import task",
            "from axm_loom import task\nfrom unrelated_helpers import task as unrelated_task",
        )
        .replace(
            "def build_node():",
            '# task("comment-decoy")\n_DECOY = \'task("string-decoy")\'\n\n\ndef build_node():',
        )
        .replace(
            'return task("build", prompt=options["prompt"])',
            'unrelated_task("homonym-decoy")\n    return task("build", prompt=options["prompt"])',
        )
    )
    project = _project(
        tmp_path / "imports",
        replacements={"src/protocols_demo/work/exec/nodes/build.py": source},
    )
    result = _category(project)
    checks = {check.name: check for check in result.checks}

    assert _CONTENT_CHECKS <= checks.keys()
    assert all(checks[name].passed for name in _CONTENT_CHECKS)


def test_finding_messages_stay_within_static_proof_boundary(tmp_path: Path) -> None:
    """AC7: findings claim only the localized observed static form."""
    project = _project(
        tmp_path / "proof-boundary",
        replacements={
            "src/protocols_demo/work/exec/nodes/build.py": (
                "from __future__ import annotations\n"
                "from pathlib import Path\n\n"
                '__all__ = ["build_node"]\n'
                'Path("effect").write_text("x")\n\n'
                "def build_node():\n    return None\n"
            )
        },
    )
    details = _details(project)

    assert "nodes/build.py:" in details
    assert "non-conform" in details
    for overclaim in (
        "decomposition relevance",
        "transitive purity",
        "runtime validity",
    ):
        assert overclaim not in details


def test_unprofiled_projects_keep_baseline_score_and_check_set(tmp_path: Path) -> None:
    """AC8: explicit protocol content checks never leak into ordinary evaluation."""
    profiled = _project(tmp_path / "profiled")
    explicit = _category(profiled)
    explicit_names = {check.name for check in explicit.checks}

    baseline_project = _project(tmp_path / "baseline", profiled=False)
    incidental_project = _project(tmp_path / "incidental", profiled=False)
    baseline = CheckEngine(baseline_project).run()
    incidental = CheckEngine(incidental_project).run()

    assert _CONTENT_CHECKS <= explicit_names
    assert baseline.score == incidental.score
    assert {check.name for check in baseline.checks} == {
        check.name for check in incidental.checks
    }
    assert not (_CONTENT_CHECKS & {check.name for check in baseline.checks})


def test_static_inspection_does_not_execute_import_time_write(tmp_path: Path) -> None:
    """AC9: a file-write finding is produced without executing inspected code."""
    sentinel = tmp_path / "sentinel-created"
    source = (
        "from __future__ import annotations\n"
        "from pathlib import Path\n"
        "from axm_loom import task\n\n"
        '__all__ = ["build_node"]\n'
        f'Path({str(sentinel)!r}).write_text("executed")\n\n'
        "def build_node():\n    return task('build', prompt='ok')\n"
    )
    project = _project(
        tmp_path / "non-executing",
        replacements={"src/protocols_demo/work/exec/nodes/build.py": source},
    )

    details = _details(project)

    assert "file write" in details or "write_text" in details
    assert "nodes/build.py:" in details
    assert not sentinel.exists()


def test_declared_prompt_without_its_resource_is_reported(tmp_path: Path) -> None:
    """A prompt named in the inventory must exist on disk as a Markdown file.

    The shared witness declares ``prompts = []``, so the prompt half of the
    resources rule was never exercised: removing the branch that reports a
    missing prompt failed nothing. This witness declares one and then withholds
    the file, which is the only shape that distinguishes a rule that reads the
    inventory from one that ignores it.
    """
    declared = _PYPROJECT.replace("prompts = []", 'prompts = ["build"]')
    with_resource = _project(
        tmp_path / "present",
        replacements={
            "src/protocols_demo/work/exec/prompts/build.md": "TODO: skeleton\n"
        },
    )
    (with_resource / "pyproject.toml").write_text(declared, encoding="utf-8")

    without_resource = _project(tmp_path / "absent")
    (without_resource / "pyproject.toml").write_text(declared, encoding="utf-8")

    present_details = _details(with_resource)
    absent_details = _details(without_resource)

    # Two rules speak about the same file and must BOTH be exercised: the
    # layout rule compares the inventory against disk, the resources rule
    # checks the declared prompt resource itself. A path-only substring
    # matches either one — and also the wheel-inclusion finding the bare
    # witness trips — so each motif is asserted on its own.
    inventory_motif = "declared prompt 'build' is missing on disk"
    resource_motif = "declared prompt resource is missing on disk"
    assert inventory_motif not in present_details
    assert resource_motif not in present_details
    assert inventory_motif in absent_details
    assert resource_motif in absent_details
