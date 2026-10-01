#!/usr/bin/env python3
"""Canonical MemSkill intermediate representation.

SHACL, Z3, and Ed25519 must consume this object. A candidate that carries
disagreeing `transitions` and `hasTransitionStep` lists is rejected.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Dict, List

UUID_V4 = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-4[0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
)
SHA256_HEX = re.compile(r"^[a-fA-F0-9]{64}$")
OPERATOR = re.compile(r"^[A-Z0-9_]+$")


class CanonicalizationError(ValueError):
    pass


def _steps_from(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        raise CanonicalizationError("step list must be a list")
    out = []
    for step in value:
        if not isinstance(step, dict):
            raise CanonicalizationError("step must be an object")
        out.append(
            {
                "stepIndex": int(step.get("stepIndex")),
                "operatorSymbol": str(step.get("operatorSymbol", "")),
                "resourceCost": int(step.get("resourceCost")),
            }
        )
    return out


def canonicalize(candidate: Dict[str, Any]) -> Dict[str, Any]:
    """Return the canonical IR or raise CanonicalizationError."""
    transitions = candidate.get("transitions")
    alt = candidate.get("hasTransitionStep")
    if transitions is None and alt is None:
        raise CanonicalizationError("missing transitions")
    left = _steps_from(transitions if transitions is not None else alt)
    if alt is not None and transitions is not None:
        right = _steps_from(alt)
        if left != right:
            raise CanonicalizationError("transitions and hasTransitionStep disagree")
    if not 1 <= len(left) <= 16:
        raise CanonicalizationError("transition count out of range")
    for step in left:
        if step["stepIndex"] < 0:
            raise CanonicalizationError("negative stepIndex")
        if not OPERATOR.match(step["operatorSymbol"]):
            raise CanonicalizationError("operatorSymbol pattern failed")
        if not 0 <= step["resourceCost"] <= 100:
            raise CanonicalizationError("resourceCost out of range")

    skill_id = str(candidate.get("skillId", ""))
    if not UUID_V4.match(skill_id):
        raise CanonicalizationError("skillId is not UUIDv4")
    score = float(candidate.get("invertibilityScore"))
    if not 0.92 <= score <= 1.0:
        raise CanonicalizationError("invertibilityScore out of range")
    timeout = int(candidate.get("maxExecutionMs"))
    if not 1 <= timeout <= 5000:
        raise CanonicalizationError("maxExecutionMs out of range")
    if candidate.get("networkAccessPermitted") is not False:
        raise CanonicalizationError("networkAccessPermitted must be false")
    digest = str(candidate.get("verificationHash", ""))
    if not SHA256_HEX.match(digest):
        raise CanonicalizationError("verificationHash is not SHA-256 hex")

    return {
        "ir_version": "memskill-ir-v1",
        "skillId": skill_id,
        "invertibilityScore": score,
        "maxExecutionMs": timeout,
        "networkAccessPermitted": False,
        "verificationHash": digest.lower(),
        "transitions": left,
    }


def canonical_bytes(ir: Dict[str, Any]) -> bytes:
    return json.dumps(ir, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def canonical_sha256(ir: Dict[str, Any]) -> str:
    return hashlib.sha256(canonical_bytes(ir)).hexdigest()
