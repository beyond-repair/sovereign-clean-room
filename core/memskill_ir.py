#!/usr/bin/env python3
"""Canonical MemSkill intermediate representation.

SHACL, Z3, and Ed25519 must consume this object. A candidate that carries
disagreeing `transitions` and `hasTransitionStep` lists is rejected.

Disagreement is a multiset difference, not a field-order difference.
`stepIndex` is the execution order. Canonical IR sorts by `stepIndex`.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Dict, List, Tuple

UUID_V4 = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-4[0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
)
SHA256_HEX = re.compile(r"^[a-fA-F0-9]{64}$")
OPERATOR = re.compile(r"^[A-Z0-9_]+$")


class CanonicalizationError(ValueError):
    pass


def _require_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise CanonicalizationError(f"{label} must be an integer")
    return value


def _step_from(step: Any) -> Dict[str, Any]:
    if not isinstance(step, dict):
        raise CanonicalizationError("step must be an object")
    try:
        index = _require_int(step.get("stepIndex"), "stepIndex")
        cost = _require_int(step.get("resourceCost"), "resourceCost")
    except CanonicalizationError:
        raise
    except Exception as exc:
        raise CanonicalizationError(f"malformed step field: {exc}") from exc
    operator = step.get("operatorSymbol")
    if not isinstance(operator, str) or not OPERATOR.match(operator):
        raise CanonicalizationError("operatorSymbol pattern failed")
    out: Dict[str, Any] = {
        "stepIndex": index,
        "operatorSymbol": operator,
        "resourceCost": cost,
    }
    if "target" in step and step["target"] is not None:
        target = step["target"]
        if not isinstance(target, str) or not OPERATOR.match(target):
            raise CanonicalizationError("invalid transition target")
        out["target"] = target
    if "targetStep" in step and step["targetStep"] is not None:
        out["targetStep"] = _require_int(step.get("targetStep"), "targetStep")
    return out


def _steps_from(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        raise CanonicalizationError("step list must be a list")
    return [_step_from(step) for step in value]


def _identity(step: Dict[str, Any]) -> Tuple[Any, ...]:
    return (
        step["stepIndex"],
        step["operatorSymbol"],
        step["resourceCost"],
        step.get("target"),
        step.get("targetStep"),
    )


def _preconditions_from(value: Any) -> List[Dict[str, str]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise CanonicalizationError("preconditions must be a list")
    out = []
    for item in value:
        if not isinstance(item, dict):
            raise CanonicalizationError("precondition must be an object")
        pid = item.get("id")
        discharged = item.get("dischargedBy")
        if not isinstance(pid, str) or not OPERATOR.match(pid):
            raise CanonicalizationError("missing or invalid precondition id")
        if not isinstance(discharged, str) or not OPERATOR.match(discharged):
            raise CanonicalizationError("missing precondition dischargedBy")
        out.append({"id": pid, "dischargedBy": discharged})
    out.sort(key=lambda p: (p["id"], p["dischargedBy"]))
    return out


def canonicalize(candidate: Dict[str, Any]) -> Dict[str, Any]:
    """Return the canonical IR or raise CanonicalizationError."""
    if not isinstance(candidate, dict):
        raise CanonicalizationError("candidate must be an object")
    transitions = candidate.get("transitions")
    alt = candidate.get("hasTransitionStep")
    if transitions is None and alt is None:
        raise CanonicalizationError("missing transitions")
    try:
        left = _steps_from(transitions if transitions is not None else alt)
        if alt is not None and transitions is not None:
            right = _steps_from(alt)
            if sorted(map(_identity, left)) != sorted(map(_identity, right)):
                raise CanonicalizationError("transitions and hasTransitionStep disagree")
    except CanonicalizationError:
        raise
    except Exception as exc:
        raise CanonicalizationError(f"malformed transitions: {exc}") from exc

    if not 1 <= len(left) <= 16:
        raise CanonicalizationError("transition count out of range")
    indexes = [step["stepIndex"] for step in left]
    if len(indexes) != len(set(indexes)):
        raise CanonicalizationError("duplicate stepIndex")
    for step in left:
        if step["stepIndex"] < 0:
            raise CanonicalizationError("negative stepIndex")
        if not 0 <= step["resourceCost"] <= 100:
            raise CanonicalizationError("resourceCost out of range")
    known = set(indexes)
    for step in left:
        if "targetStep" in step and step["targetStep"] not in known and step["targetStep"] != -1:
            raise CanonicalizationError("invalid transition target")

    skill_id = candidate.get("skillId")
    if not isinstance(skill_id, str) or not UUID_V4.match(skill_id):
        raise CanonicalizationError("skillId is not UUIDv4")
    try:
        score = float(candidate.get("invertibilityScore"))
    except (TypeError, ValueError) as exc:
        raise CanonicalizationError("invertibilityScore malformed") from exc
    if isinstance(candidate.get("invertibilityScore"), bool) or not 0.92 <= score <= 1.0:
        raise CanonicalizationError("invertibilityScore out of range")
    try:
        timeout = _require_int(candidate.get("maxExecutionMs"), "maxExecutionMs")
    except CanonicalizationError:
        raise
    except Exception as exc:
        raise CanonicalizationError("maxExecutionMs malformed") from exc
    if not 1 <= timeout <= 5000:
        raise CanonicalizationError("maxExecutionMs out of range")
    if candidate.get("networkAccessPermitted") is not False:
        raise CanonicalizationError("networkAccessPermitted must be false")
    digest = candidate.get("verificationHash")
    if not isinstance(digest, str) or not SHA256_HEX.match(digest):
        raise CanonicalizationError("verificationHash is not SHA-256 hex")

    preconditions = _preconditions_from(candidate.get("preconditions"))
    ordered = sorted(left, key=_identity)
    return {
        "ir_version": "memskill-ir-v1",
        "skillId": skill_id,
        "invertibilityScore": score,
        "maxExecutionMs": timeout,
        "networkAccessPermitted": False,
        "verificationHash": digest.lower(),
        "preconditions": preconditions,
        "transitions": ordered,
    }


def canonical_bytes(ir: Dict[str, Any]) -> bytes:
    return json.dumps(ir, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def canonical_sha256(ir: Dict[str, Any]) -> str:
    return hashlib.sha256(canonical_bytes(ir)).hexdigest()
