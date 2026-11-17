"""Canonical evidence for trusted Codex host tool calls."""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Mapping

__all__ = ["PROOF_FIELD", "argument_digest", "sign_proof", "verify_proof"]

PROOF_FIELD = "_axm_host_proof"
_MAX_PAYLOAD = 131072
_MIN_KEY_LENGTH = 32
_DOMAIN = b"axm-warden-codex-host-proof-v1\0"


def _canonical(value: object) -> bytes:
    data = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    if len(data) > _MAX_PAYLOAD:
        raise ValueError("proof input too large")
    return data


def argument_digest(arguments: Mapping[str, object]) -> str:
    """Bind exact cleaned MCP arguments without using them as an identity."""
    return hashlib.sha256(_canonical(arguments)).hexdigest()


def sign_proof(key: str, body: Mapping[str, object]) -> dict[str, object]:
    """Sign a versioned host invocation using a dedicated operator key."""
    if len(key) < _MIN_KEY_LENGTH:
        raise ValueError("invalid proof key")
    signature = hmac.new(key.encode(), _DOMAIN + _canonical(body), hashlib.sha256)
    return {"body": dict(body), "signature": signature.hexdigest()}


def verify_proof(key: str, proof: object) -> dict[str, object]:
    """Authenticate and return a strictly structured proof."""
    if not isinstance(proof, dict) or set(proof) != {"body", "signature"}:
        raise ValueError("invalid host proof")
    body, signature = proof["body"], proof["signature"]
    if not isinstance(body, dict) or not isinstance(signature, str):
        raise ValueError("invalid host proof")
    expected = sign_proof(key, body)["signature"]
    if not isinstance(expected, str) or not hmac.compare_digest(expected, signature):
        raise ValueError("invalid host proof")
    return body
