"""Orphan-import detection for ``batch_edit`` operation sets.

A ``batch_edit`` applies a set of file operations atomically, but ruff's
``F401`` autofix may run *between* the moment an import is added and the moment
its consumer is added in a later, separate edit — stripping the freshly-added
import as "unused" and breaking the eventual consumer.

This module provides a deterministic, read-only detector that inspects a single
``batch_edit`` operation set and flags any import added *without a consumer in
the same atomic batch*. It performs no mutation, no auto-fix and no re-ordering:
it only reports.

Parsing and import extraction are delegated to ``axm-ast`` primitives
(``parse_source`` + ``_extract_imports``) rather than a hand-rolled tokenizer, so
the detector tracks the exact Python grammar ``axm-ast`` already understands.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from axm_ast.core.parser import _extract_imports, parse_source
from pydantic import BaseModel, ConfigDict, Field, computed_field

__all__ = [
    "ImportGuardReport",
    "OrphanImportViolation",
    "detect_orphan_imports",
]

# Tree-sitter node types that represent an import statement. Their subtrees are
# skipped when collecting *consumer* identifiers, so an import never counts as
# its own consumer.
_IMPORT_NODE_TYPES = frozenset(
    {"import_statement", "import_from_statement", "future_import_statement"}
)


class OrphanImportViolation(BaseModel):  # type: ignore[explicit-any]  # pydantic synthesizes __init__(**data: Any)
    """A single import added without any in-batch consumer.

    Example:
        >>> v = OrphanImportViolation(
        ...     file="a.py", imported_name="os", reason="no consumer"
        ... )
        >>> v.imported_name
        'os'
    """

    model_config = ConfigDict(extra="forbid")

    file: str = Field(description="File (relative path) the import was added to")
    imported_name: str = Field(description="The imported symbol with no consumer")
    reason: str = Field(description="Human-readable explanation of the violation")


class ImportGuardReport(BaseModel):  # type: ignore[explicit-any]  # pydantic synthesizes __init__(**data: Any)
    """Structured verdict of :func:`detect_orphan_imports`.

    Example:
        >>> ImportGuardReport().verdict
        True
    """

    model_config = ConfigDict(extra="forbid")

    violations: list[OrphanImportViolation] = Field(
        default_factory=list, description="Every orphan-import violation found"
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def verdict(self) -> bool:
        """``True`` when no violation was found (the batch is clean)."""
        return not self.violations


def _text_of(node: object) -> str | None:
    """Decode a tree-sitter node's UTF-8 text, tolerating missing bytes."""
    raw = getattr(node, "text", None)
    if isinstance(raw, bytes):
        return raw.decode("utf-8")
    return None


def _bound_pairs(node_type: str, info: object) -> list[tuple[str, str]]:
    """Map an ``ImportInfo`` to ``(imported_name, bound_name)`` pairs.

    ``bound_name`` is the identifier a consumer would reference; ``imported_name``
    is the symbol as written in the source (reported in the violation).
    """
    names: Sequence[str] = getattr(info, "names", [])
    alias: str | None = getattr(info, "alias", None)
    if node_type == "import_statement":
        name = names[0] if names else ""
        bound = alias if alias else name.split(".")[0]
        return [(name, bound)] if name else []
    pairs: list[tuple[str, str]] = []
    for name in names:
        if not name or name == "*":
            continue
        pairs.append((name, alias if alias else name))
    return pairs


def _iter_added_imports(source: str) -> list[tuple[str, str]]:
    """Return ``(imported_name, bound_name)`` for every import in ``source``."""
    tree = parse_source(source)
    pairs: list[tuple[str, str]] = []
    stack = [tree.root_node]
    while stack:
        node = stack.pop()
        if node.type in _IMPORT_NODE_TYPES:
            for info in _extract_imports(node):
                pairs.extend(_bound_pairs(node.type, info))
            continue
        stack.extend(node.children)
    return pairs


def _used_names(source: str) -> set[str]:
    """Collect identifiers used *outside* import statements in ``source``."""
    tree = parse_source(source)
    used: set[str] = set()
    stack = [tree.root_node]
    while stack:
        node = stack.pop()
        if node.type in _IMPORT_NODE_TYPES:
            continue
        if node.type == "identifier":
            text = _text_of(node)
            if text is not None:
                used.add(text)
        stack.extend(node.children)
    return used


def _op_sources(op: Mapping[str, object]) -> tuple[str, str, str]:
    """Return ``(file, added_source, context_source)`` for one operation.

    ``added_source`` is code introduced by the batch (``create`` content or
    ``replace`` new text); ``context_source`` is pre-existing code the batch
    keeps around (``replace`` old text) — a legitimate consumer surface that
    must not be mistaken for an orphan.
    """
    file = str(op.get("file", ""))
    kind = op.get("op")
    if kind == "create":
        content = op.get("content", "")
        return file, content if isinstance(content, str) else "", ""
    if kind == "replace":
        edits = op.get("edits", [])
        added: list[str] = []
        context: list[str] = []
        if isinstance(edits, list):
            for edit in edits:
                if not isinstance(edit, Mapping):
                    continue
                new = edit.get("new", "")
                old = edit.get("old", "")
                if isinstance(new, str):
                    added.append(new)
                if isinstance(old, str):
                    context.append(old)
        return file, "\n".join(added), "\n".join(context)
    return file, "", ""


def detect_orphan_imports(
    operation_set: Mapping[str, object],
) -> ImportGuardReport:
    """Flag imports added by a ``batch_edit`` op set with no in-batch consumer.

    The detector is pure (no mutation, no I/O on the target project): it reads
    only the operation set. An import is an orphan when the identifier it binds
    is used *nowhere* across the batch — neither in the batch's own additions nor
    in the pre-existing code the batch retains (``replace`` old text). Consumers
    landing in the *same* operation set — in any file — suppress the violation.

    Args:
        operation_set: The ``{path, operations: [{op, file, edits|content}]}``
            mapping ``batch_edit`` consumes.

    Returns:
        An :class:`ImportGuardReport` whose ``verdict`` is ``True`` iff clean.
    """
    operations = operation_set.get("operations", [])
    if not isinstance(operations, Sequence):
        return ImportGuardReport()

    consumers: set[str] = set()
    added_imports: list[tuple[str, str, str]] = []
    for op in operations:
        if not isinstance(op, Mapping):
            continue
        file, added, context = _op_sources(op)
        consumers |= _used_names(added)
        consumers |= _used_names(context)
        # Only imports introduced by the batch are candidates: an import present
        # in the pre-existing (``old``) text is retained, not added, so it must
        # never be flagged (no false positive on pre-existing imports).
        pre_existing = set(_iter_added_imports(context))
        for imported_name, bound in _iter_added_imports(added):
            if (imported_name, bound) not in pre_existing:
                added_imports.append((file, imported_name, bound))

    violations = [
        OrphanImportViolation(
            file=file,
            imported_name=imported_name,
            reason=(
                f"'{imported_name}' is imported but no consumer of "
                f"'{bound}' appears anywhere in the batch additions"
            ),
        )
        for file, imported_name, bound in added_imports
        if bound not in consumers
    ]
    return ImportGuardReport(violations=violations)
