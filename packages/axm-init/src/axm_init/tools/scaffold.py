"""InitScaffoldTool — project scaffolding as an AXMTool."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from axm.tools.base import ToolResult

if TYPE_CHECKING:
    from axm_init.adapters.workspace_patcher import PatchReport

from axm_init.core.scaffolder import (
    build_member_data,
    read_workspace_name,
    resolve_workspace_root,
)

__all__ = ["InitScaffoldTool", "read_workspace_name"]


SCAFFOLD_KINDS: tuple[str, ...] = (
    "standalone",
    "workspace",
    "member",
    "paper",
    "experiment",
)

_SLUG_ALPHA = "abcdefghijklmnopqrstuvwxyz"
_SLUG_ALLOWED = _SLUG_ALPHA + "0123456789"


def _read_kind(kwargs: dict[str, object]) -> str | None:
    """Read the declared scaffold ``kind`` from *kwargs*, or ``None``."""
    value = kwargs.get("kind")
    return value if isinstance(value, str) and value else None


def _apply_kind_flags(
    kind: str | None,
    *,
    workspace: bool,
    member: str | None,
    name: str | None,
) -> tuple[bool, str | None]:
    """Map the declared *kind* onto the legacy workspace/member flags."""
    if kind == "workspace":
        return True, member
    if kind == "member":
        return workspace, member or name
    return workspace, member


def _slugify(value: str) -> str:
    """Return *value* as a template-safe slug matching ``^[a-z][a-z0-9-]*$``."""
    cleaned = "".join(c if c in _SLUG_ALLOWED else "-" for c in value.strip().lower())
    slug = "-".join(part for part in cleaned.split("-") if part) or "untitled"
    return slug if slug[0] in _SLUG_ALPHA else f"x-{slug}"


def _ensure_experiments_root(paper_root: Path) -> list[str]:
    """Create the paper's ``experiments/`` root and return the files created.

    The experiments root belongs to this tool — it names and indexes every
    experiment directory — never to the paper template, which renders flat.
    """
    experiments = paper_root / "experiments"
    experiments.mkdir(parents=True, exist_ok=True)
    placeholder = experiments / ".gitkeep"
    if not placeholder.exists():
        placeholder.write_text("")
    return ["experiments/.gitkeep"]


def _group_files(files: list[str]) -> list[str]:
    """Group created files by top-level dir, listing basenames inline.

    Compact companion to the ``files`` list in the scaffold ToolResult data:
    every file is kept verbatim, only grouped by its first path segment to
    drop repeated directory prefixes. Files at the root are grouped under ``.``.
    """
    groups: dict[str, list[str]] = defaultdict(list)
    for f in files:
        head, sep, tail = f.partition("/")
        if sep:
            groups[f"{head}/"].append(tail)
        else:
            groups["."].append(head)
    return [f"{prefix} : {' '.join(names)}" for prefix, names in groups.items()]


def _render_scaffold_text(
    *,
    label: str,
    kind: str,
    files: list[str],
    path: str | None = None,
    report: PatchReport | None = None,
) -> str:
    """Render a scaffold result as compact text.

    Header carries the package label, kind and file count; optional ``path``
    and — when a member patch ran — ``patched`` / ``skipped`` / ``failed``
    lines surface member location and the truthful patch outcome (only real
    writes appear under ``patched``); then one line per top-level dir lists
    every created file. Nothing is dropped — this is the LLM-facing companion
    to the structured ToolResult data.
    """
    lines = [f"init_scaffold | ✓ | {label} ({kind}) | {len(files)} files"]
    if path:
        lines.append(f"path: {path}")
    if report and report.patched:
        lines.append(f"patched root: {', '.join(report.patched)}")
    if report and report.skipped:
        lines.append(f"skipped root: {', '.join(report.skipped)}")
    if report and report.failed:
        lines.append(f"failed root: {', '.join(report.failed)}")
    lines.extend(_group_files(files))
    return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class _ProjectMeta:
    org: str
    license_type: str
    author_name: str
    author_email: str


class InitScaffoldTool:
    """Initialize a new Python project with best practices.

    Registered as ``init_scaffold`` via axm.tools entry point.
    """

    @property
    def name(self) -> str:
        """Tool name used for MCP registration."""
        return "init_scaffold"

    @property
    def kinds(self) -> tuple[str, ...]:
        """Scaffold kinds this tool declares, in template order.

        The declared set is the tool's contract: every value is selectable
        through the ``kind`` input (MCP) and ``--kind`` (CLI), and each one
        maps to a bundled Copier template.
        """
        return SCAFFOLD_KINDS

    def _validate_inputs(
        self,
        kwargs: dict[str, object],
    ) -> (
        tuple[str, str | None, str, str, str, str, str, bool, str | None, str | None]
        | ToolResult
    ):
        """Extract and validate inputs from kwargs.

        Returns a tuple of validated values or a ToolResult on error.
        """

        def _str(key: str, default: str = "") -> str:
            v = kwargs.get(key, default)
            return v if isinstance(v, str) else default

        def _opt_str(key: str) -> str | None:
            v = kwargs.get(key)
            return v if isinstance(v, str) else None

        path: str = _str("path", ".")
        name: str | None = _opt_str("name")
        org: str = _str("org")
        author: str = _str("author")
        email: str = _str("email")
        license_type: str = _str("license", "Apache-2.0")
        license_holder: str | None = _opt_str("license_holder")
        description: str = _str("description")
        workspace_raw = kwargs.get("workspace", False)
        if not isinstance(workspace_raw, bool):
            return ToolResult(
                success=False,
                error=(
                    f"'workspace' must be a boolean, got {type(workspace_raw).__name__}"
                ),
            )
        workspace: bool = workspace_raw
        member: str | None = _opt_str("member")

        if not org or not author or not email:
            return ToolResult(
                success=False,
                error="org, author, and email are required",
            )

        if workspace and member is not None:
            return ToolResult(
                success=False,
                error="'workspace' and 'member' are mutually exclusive",
            )

        return (
            path,
            name,
            org,
            author,
            email,
            license_type,
            description,
            workspace,
            member,
            license_holder,
        )

    def _build_template_data(
        self,
        *,
        project_name: str,
        workspace: bool,
        description: str,
        meta: _ProjectMeta,
    ) -> dict[str, str]:
        """Build template data dict for workspace or standalone scaffold."""
        name_key = "workspace_name" if workspace else "package_name"
        default_desc = (
            "A modern Python workspace" if workspace else "A modern Python package"
        )
        return {
            name_key: project_name,
            "description": description or default_desc,
            "org": meta.org,
            "license": meta.license_type,
            "license_holder": meta.org,
            "author_name": meta.author_name,
            "author_email": meta.author_email,
        }

    def execute(self, **kwargs: object) -> ToolResult:
        """Initialize a new Python project.

        Args:
            **kwargs: Keyword arguments.
                path: Path to initialize project.
                name: Project name (defaults to directory name).
                org: GitHub org or username.
                author: Author name.
                email: Author email.
                license: License type.
                license_holder: License holder (defaults to org).
                description: Project description.
                workspace: If True, scaffold a UV workspace.
                member: Member package name to scaffold inside a workspace.
                kind: Explicit scaffold kind — one of ``SCAFFOLD_KINDS``
                    (standalone, workspace, member, paper, experiment).

        Returns:
            ToolResult with created files list.
        """
        validated = self._validate_inputs(kwargs)
        if isinstance(validated, ToolResult):
            return validated

        (
            path,
            name,
            org,
            author,
            email,
            license_type,
            description,
            workspace,
            member,
            license_holder,
        ) = validated

        kind = _read_kind(kwargs)
        if kind is not None and kind not in SCAFFOLD_KINDS:
            return ToolResult(
                success=False,
                error=(
                    f"Unknown kind '{kind}' — expected one of "
                    f"{', '.join(SCAFFOLD_KINDS)}"
                ),
            )
        workspace, member = _apply_kind_flags(
            kind, workspace=workspace, member=member, name=name
        )

        try:
            target_path = Path(path).resolve()
            meta = _ProjectMeta(
                org=org,
                license_type=license_type,
                author_name=author,
                author_email=email,
            )

            dispatched = self._dispatch_kind(
                kind,
                target_path=target_path,
                name=name,
                description=description,
                meta=meta,
            )
            if dispatched is not None:
                return dispatched

            if member:
                return self._scaffold_member(
                    target_path,
                    member,
                    scaffold_data={
                        "org": org,
                        "author_name": author,
                        "author_email": email,
                        "license": license_type,
                        "description": description,
                    },
                    license_holder=license_holder,
                )

            project_name = name or target_path.name

            from axm_init.adapters.copier import CopierAdapter, CopierConfig
            from axm_init.core.templates import TemplateType, get_template_path

            template_type = (
                TemplateType.WORKSPACE if workspace else TemplateType.STANDALONE
            )
            data = self._build_template_data(
                project_name=project_name,
                workspace=workspace,
                description=description,
                meta=meta,
            )

            copier_adapter = CopierAdapter()
            copier_config = CopierConfig(
                template_path=get_template_path(template_type),
                destination=target_path,
                data=data,
                trust_template=True,
            )
            result = copier_adapter.copy(copier_config)

            files = [str(f) for f in result.files_created]
            return ToolResult(
                success=result.success,
                data={
                    "project_name": project_name,
                    "template": template_type.value,
                    "files": files,
                },
                text=(
                    _render_scaffold_text(
                        label=project_name,
                        kind=template_type.value,
                        files=files,
                    )
                    if result.success
                    else None
                ),
                error=None if result.success else result.message,
            )
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))

    def _dispatch_kind(
        self,
        kind: str | None,
        *,
        target_path: Path,
        name: str | None,
        description: str,
        meta: _ProjectMeta,
    ) -> ToolResult | None:
        """Route the paper and experiment kinds.

        Returns ``None`` when *kind* is not one of them, so the caller falls
        through to the member / workspace / standalone cascade.
        """
        label = name or target_path.name
        if kind == "paper":
            return self._scaffold_paper(
                target_path,
                paper_name=label,
                meta=meta,
                description=description,
            )
        if kind == "experiment":
            return self._scaffold_experiment(
                target_path,
                experiment_name=label,
                description=description,
            )
        return None

    def _scaffold_paper(
        self,
        target_path: Path,
        *,
        paper_name: str,
        meta: _ProjectMeta,
        description: str,
    ) -> ToolResult:
        """Scaffold a paper submodule at *target_path*.

        Renders the bundled paper template, then materialises the
        ``experiments/`` root this tool owns (the template renders flat and
        never names an experiment directory).

        Args:
            target_path: Directory the paper is rendered into.
            paper_name: Human-supplied paper name, slugified for the template.
            meta: Author/license identity for the template variables.
            description: Paper title; falls back to *paper_name*.

        Returns:
            ToolResult with the created files list.
        """
        from axm_init.adapters.copier import CopierAdapter, CopierConfig
        from axm_init.core.templates import TemplateType, get_template_path

        slug = _slugify(paper_name)
        result = CopierAdapter().copy(
            CopierConfig(
                template_path=get_template_path(TemplateType.PAPER),
                destination=target_path,
                data={
                    "paper_name": slug,
                    "title": description or paper_name,
                    "author": meta.author_name,
                },
                trust_template=True,
            )
        )
        if not result.success:
            return ToolResult(
                success=False,
                error=result.message or "Paper scaffold failed",
            )

        files = sorted({*result.files_created, *_ensure_experiments_root(target_path)})
        kind = TemplateType.PAPER.value
        return ToolResult(
            success=True,
            data={
                "project_name": slug,
                "template": kind,
                "path": str(target_path),
                "files": files,
            },
            text=_render_scaffold_text(
                label=slug,
                kind=kind,
                files=files,
                path=str(target_path),
            ),
        )

    def _scaffold_experiment(
        self,
        target_path: Path,
        *,
        experiment_name: str,
        description: str,
    ) -> ToolResult:
        """Scaffold an indexed experiment inside the paper at *target_path*.

        Guards on the detected context first: an experiment is legal only
        inside a detected paper, and the guard fails before any write. The
        directory is named ``{index:02d}-{slug}`` with the next free index.

        Args:
            target_path: The paper root the experiment belongs to.
            experiment_name: Human-supplied experiment name, slugified.
            description: Experiment title / research question fallback.

        Returns:
            ToolResult with the created files list, relative to the paper.
        """
        from axm_init.adapters.copier import CopierAdapter, CopierConfig
        from axm_init.checks._workspace import ProjectContext, detect_context
        from axm_init.core.scaffolder import next_experiment_index
        from axm_init.core.templates import TemplateType, get_template_path

        if detect_context(target_path) != ProjectContext.PAPER:
            return ToolResult(
                success=False,
                error=(
                    f"{target_path} is not a paper — scaffold a paper first "
                    "(kind='paper')"
                ),
            )

        experiments_dir = target_path / "experiments"
        index = next_experiment_index(experiments_dir)
        experiment_dir = experiments_dir / f"{index:02d}-{_slugify(experiment_name)}"
        title = description or experiment_name

        result = CopierAdapter().copy(
            CopierConfig(
                template_path=get_template_path(TemplateType.EXPERIMENT),
                destination=experiment_dir,
                data={
                    "experiment_id": experiment_dir.name,
                    "experiment_title": title,
                    "research_question": (
                        description or f"What does '{title}' establish?"
                    ),
                },
                trust_template=True,
            )
        )
        if not result.success:
            return ToolResult(
                success=False,
                error=result.message or "Experiment scaffold failed",
            )

        prefix = experiment_dir.relative_to(target_path).as_posix()
        files = [f"{prefix}/{f}" for f in result.files_created]
        kind = TemplateType.EXPERIMENT.value
        return ToolResult(
            success=True,
            data={
                "experiment": experiment_dir.name,
                "template": kind,
                "path": str(experiment_dir),
                "index": index,
                "files": files,
            },
            text=_render_scaffold_text(
                label=experiment_dir.name,
                kind=kind,
                files=files,
                path=str(experiment_dir),
            ),
        )

    @staticmethod
    def _resolve_workspace_root(target_path: Path) -> Path | None:
        """Resolve workspace root from target path, or None if not in a workspace."""
        return resolve_workspace_root(target_path)

    def _scaffold_member(
        self,
        target_path: Path,
        member_name: str,
        *,
        scaffold_data: dict[str, str],
        license_holder: str | None = None,
    ) -> ToolResult:
        """Scaffold a member sub-package inside an existing workspace.

        Args:
            target_path: Current directory (must be inside a workspace).
            member_name: Name of the new member package.
            scaffold_data: Template variables (org, author, email, etc.).
            license_holder: Explicit LICENSE holder; falls back to ``org``.

        Returns:
            ToolResult with member scaffold results.
        """
        from axm_init.adapters.copier import CopierAdapter, CopierConfig
        from axm_init.adapters.workspace_patcher import patch_all
        from axm_init.core.templates import TemplateType, get_template_path

        workspace_root = self._resolve_workspace_root(target_path)
        if workspace_root is None:
            return ToolResult(success=False, error="Not inside a UV workspace")

        member_dir = workspace_root / "packages" / member_name
        if member_dir.exists():
            return ToolResult(
                success=False,
                error=f"Member '{member_name}' already exists at {member_dir}",
            )

        data = build_member_data(
            member_name,
            read_workspace_name(workspace_root),
            scaffold_data,
            license_holder=license_holder,
        )

        copier_adapter = CopierAdapter()
        copier_config = CopierConfig(
            template_path=get_template_path(TemplateType.MEMBER),
            destination=member_dir,
            data=data,
            trust_template=True,
        )
        result = copier_adapter.copy(copier_config)

        if not result.success:
            return ToolResult(
                success=False,
                error=result.message or "Member scaffold failed",
            )

        report = patch_all(workspace_root, member_name)

        files = [str(f) for f in result.files_created]
        return ToolResult(
            success=True,
            data={
                "member": member_name,
                "path": str(member_dir),
                "files": files,
                "patched_root_files": report.patched,
                "skipped_root_files": report.skipped,
                "failed_root_files": report.failed,
            },
            text=_render_scaffold_text(
                label=member_name,
                kind="member",
                files=files,
                path=str(member_dir),
                report=report,
            ),
        )
