"""Pure AST structural-similarity helpers (Jaccard over statement-sets).

Moved verbatim from ``axm-audit``'s ``duplicate_tests`` rule (AXM-2172 / E5):
the similarity primitives are corpus-agnostic and 100% structural — they parse
an ``ast.FunctionDef``, normalize away constant/identifier identity, and compare
the resulting statement-sets with Jaccard. No embedding backend is involved and
**torch is never imported** on this path (it lives behind the optional ``neural``
extra, used only by :mod:`axm_echo.embedding`).

The audit ``duplicate_tests`` rule imports these helpers directly (a ~50ms pure
structural import, no torch → a legitimate direct import, not ``axm_call``).
"""

from __future__ import annotations

import ast
import re

__all__ = [
    "flatten_body",
    "jaccard_similarity",
    "normalize_dump",
    "statement_set",
]

_CONSTANT_RE = re.compile(r"Constant\([^()]*\)")
_NAME_RE = re.compile(r"Name\('[^']*',")


def flatten_body(body: list[ast.stmt]) -> list[ast.stmt]:
    """Flatten compound statements (with/if/for/while/try) into their inner body."""
    out: list[ast.stmt] = []
    for stmt in body:
        match stmt:
            case ast.With() | ast.AsyncWith():
                out.extend(flatten_body(stmt.body))
            case ast.If() | ast.For() | ast.While() | ast.AsyncFor():
                out.extend(flatten_body(stmt.body))
                out.extend(flatten_body(stmt.orelse))
            case ast.Try():
                out.extend(flatten_body(stmt.body))
                for handler in stmt.handlers:
                    out.extend(flatten_body(handler.body))
                out.extend(flatten_body(stmt.orelse))
                out.extend(flatten_body(stmt.finalbody))
            case _:
                out.append(stmt)
    return out


def statement_set(node: ast.FunctionDef) -> frozenset[str]:
    """Normalized stmt shapes (constants + name ids replaced) as a set."""
    stmts: set[str] = set()
    for stmt in flatten_body(node.body):
        try:
            dump = ast.dump(stmt, annotate_fields=False)
        except Exception:  # noqa: BLE001, S112
            continue
        dump = _CONSTANT_RE.sub("Constant(<C>)", dump)
        dump = _NAME_RE.sub("Name(<N>,", dump)
        stmts.add(dump)
    return frozenset(stmts)


def normalize_dump(stmt: ast.stmt) -> str | None:
    """Normalized single-statement dump (constants + name ids replaced)."""
    try:
        dump = ast.dump(stmt, annotate_fields=False)
    except Exception:  # noqa: BLE001
        return None
    dump = _CONSTANT_RE.sub("Constant(<C>)", dump)
    dump = _NAME_RE.sub("Name(<N>,", dump)
    return dump


def jaccard_similarity(
    a: set[str] | frozenset[str], b: set[str] | frozenset[str]
) -> float:
    """Jaccard similarity between two sets (1.0 when both are empty)."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0
