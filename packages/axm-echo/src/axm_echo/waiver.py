"""Acknowledged-cluster waiver mechanism, factored and key-schema agnostic.

This is the *single* implementation of the cluster-acknowledgement contract
used by the AXM duplicate-detection tools. It is intentionally parametrizable
by the **key schema** that identifies a cluster member, so the same hash and
the same mark/stale/validate logic serve different callers:

* ``echo_code`` hashes a cluster on its members' ``(package, qualname)``;
* ``duplicate_tests`` (audit) hashes on ``(file, name)``.

The algorithm is ported byte-for-byte (modulo the key parameter) from
``axm_audit.core.rules.test_quality.duplicate_tests`` so the two tools agree
on what a cluster hash *is* -- the anti-duplication tool must not duplicate its
own waiver mechanism. A later ticket may have ``duplicate_tests`` import this
module to drop its private copy; that migration is out of scope here.

The contract:

* :func:`cluster_hash` -- order-independent 12-hex digest of a cluster's member
  key set (members sorted before serialization, so the hash is robust to
  ordering and to line drift, sensitive only to membership).
* :func:`validate_acknowledged_entry` -- graceful schema validation: returns an
  error *message* for a malformed waiver, ``None`` when valid; never raises.
* :func:`mark_acknowledged` -- stamps ``acknowledged=True`` on every live
  cluster whose ``cluster_hash`` is waived.
* :func:`stale_acknowledged` -- the virtuous half: waivers whose hash matches
  no live cluster ("this waiver no longer serves a purpose, retire it").
* :func:`extract_acknowledged_section` -- pull the ``[[tool.<tool>.<rule>]]``
  acknowledged table out of a parsed pyproject mapping.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

__all__ = [
    "HASH_LEN",
    "cluster_hash",
    "extract_acknowledged_section",
    "mark_acknowledged",
    "stale_acknowledged",
    "validate_acknowledged_entry",
]

# A cluster hash is the first 12 hex chars of a sha256 -- short enough to paste
# into a pyproject waiver, wide enough to avoid collisions across a corpus.
HASH_LEN = 12
_HASH_HEX_PATTERN = re.compile(rf"^[0-9a-f]{{{HASH_LEN}}}$")


def cluster_hash(cluster: Mapping[str, object], *, key_fields: Sequence[str]) -> str:
    """Compute a stable 12-hex-char hash of a cluster's member key set.

    The hash is order-independent (members are sorted before serialization) and
    depends only on ``key_fields`` -- the chosen identity of a member. For
    ``echo_code`` pass ``key_fields=("package", "qualname")``; for the audit
    duplicate-tests rule pass ``("file", "name")``. Two clusters with the same
    membership under the same key schema hash identically; the same membership
    under a *different* key schema hashes differently.

    Args:
        cluster: A mapping carrying a ``"members"`` list of member mappings.
        key_fields: The member fields, in order, that define member identity.

    Returns:
        The first :data:`HASH_LEN` hex chars of the sha256 of the sorted,
        canonically-serialized member key tuples.
    """
    raw_members = cluster.get("members", [])
    members = raw_members if isinstance(raw_members, list) else []
    keyed: list[list[str]] = sorted(
        [str(member.get(field, "")) for field in key_fields] for member in members
    )
    blob = json.dumps(keyed, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:HASH_LEN]


def validate_acknowledged_entry(entry: object) -> str | None:
    """Validate one acknowledged-waiver entry; return an error or ``None``.

    A valid entry is a table with a 12-char hex ``hash`` and a non-empty
    ``reason``. On any violation an explanatory message is returned (never an
    exception) so the caller can surface it gracefully instead of crashing.

    Args:
        entry: The raw waiver entry parsed from the pyproject.

    Returns:
        An error message string if the entry is malformed, else ``None``.
    """
    if not isinstance(entry, dict):
        return "acknowledged entry must be a table (schema error)"
    hash_val = entry.get("hash")
    if not isinstance(hash_val, str) or not _HASH_HEX_PATTERN.match(hash_val):
        return "acknowledged.hash must be a 12-char hex string (schema error)"
    reason_val = entry.get("reason")
    if not isinstance(reason_val, str) or not reason_val.strip():
        return "acknowledged.reason must be a non-empty string (schema error)"
    return None


def mark_acknowledged(
    clusters: list[dict[str, object]], acknowledged: list[dict[str, str]]
) -> None:
    """Stamp ``acknowledged=True`` on every live cluster that is waived.

    A cluster is waived when its ``"cluster_hash"`` appears among the waiver
    hashes. Mutates the cluster mappings in place.

    Args:
        clusters: Live clusters, each carrying a ``"cluster_hash"``.
        acknowledged: Validated waiver entries (each with a ``"hash"``).
    """
    hashes = {entry["hash"] for entry in acknowledged}
    for cluster in clusters:
        if cluster.get("cluster_hash") in hashes:
            cluster["acknowledged"] = True


def stale_acknowledged(
    clusters: list[dict[str, object]], acknowledged: list[dict[str, str]]
) -> list[dict[str, str]]:
    """Return the waivers whose hash matches no live cluster (stale, retirable).

    This is the virtuous half of the mechanism: a waiver that no longer covers
    any live cluster is dead weight and should be removed from the pyproject.
    Informative only -- it never blocks.

    Args:
        clusters: Live clusters, each carrying a ``"cluster_hash"``.
        acknowledged: Validated waiver entries (each with a ``"hash"``).

    Returns:
        The subset of ``acknowledged`` whose hash is not in any live cluster.
    """
    live = {c["cluster_hash"] for c in clusters if "cluster_hash" in c}
    return [entry for entry in acknowledged if entry["hash"] not in live]


def extract_acknowledged_section(data: object, *, tool: str, rule: str) -> object:
    """Pull the ``[[tool.<tool>.<rule>]]`` acknowledged table from a pyproject.

    Walks ``data["tool"][tool][rule]`` defensively: any missing or non-mapping
    level yields ``{}`` so a malformed or absent section degrades gracefully.

    Args:
        data: The parsed pyproject mapping (or anything, defensively).
        tool: The tool table name (e.g. ``"axm-echo"``).
        rule: The rule/section name (e.g. ``"acknowledged"``).

    Returns:
        The nested section value, or ``{}`` when any level is absent/invalid.
    """
    if not isinstance(data, dict):
        return {}
    tool_table = data.get("tool", {})
    if not isinstance(tool_table, dict):
        return {}
    tool_section = tool_table.get(tool, {})
    if not isinstance(tool_section, dict):
        return {}
    return tool_section.get(rule, {})
