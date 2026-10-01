#!/usr/bin/env python3
"""Runtime trace of a canonical MemSkill IR.

Z3 SAT is not this interpreter. The two are compared by the correspondence
matrix in the locked protocol. This interpreter is the runtime label.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Optional, Set, Tuple


def execute_trace(
    skill_data: Dict[str, Any],
    max_resource_capacity: int = 100,
    observed_external: Optional[Iterable[str]] = None,
) -> Tuple[str, str]:
    """Return (SAFE|UNSAFE, reason).

    Semantics match the Z3 frame for isolate / verify / execute, resource
    sum, and final verification. EXTERNAL preconditions are SAFE only when
    the caller observed that attestation. Z3 does not model that observation.
    """
    steps = list(skill_data.get("transitions") or [])
    if not steps:
        return "UNSAFE", "empty transition pipeline"
    steps.sort(key=lambda s: (int(s.get("stepIndex", 0)), str(s.get("operatorSymbol", ""))))
    observed: Set[str] = set(observed_external or [])
    operators = [str(step.get("operatorSymbol", "")) for step in steps]
    for prec in skill_data.get("preconditions") or []:
        discharged = str(prec.get("dischargedBy", ""))
        pid = str(prec.get("id", ""))
        if discharged == "EXTERNAL":
            if pid not in observed:
                return "UNSAFE", f"external precondition {pid} not observed"
            continue
        if discharged not in operators:
            return "UNSAFE", f"precondition {pid} not discharged by a transition"

    isolated = False
    verified = False
    total = 0
    for step in steps:
        cost = int(step.get("resourceCost", 0))
        if cost < 0:
            return "UNSAFE", "negative resource cost"
        total += cost
        if total > max_resource_capacity:
            return "UNSAFE", "resource bound exceeded"
        op = str(step.get("operatorSymbol", ""))
        if op == "ISOLATE_ENVIRONMENT":
            isolated = True
        elif op == "VERIFY_INTEGRITY":
            if not isolated:
                return "UNSAFE", "verify without isolation"
            verified = True
        elif op == "EXECUTE_PRIMITIVE":
            if not (isolated and verified):
                return "UNSAFE", "execute without isolation and verification"
        # Other operators preserve isolation and verification.
    if not verified:
        return "UNSAFE", "final state not verified"
    return "SAFE", "trace satisfied isolation, verification, execution, and resource bounds"


def correspondence(z3_safe: bool, runtime_label: str) -> Dict[str, str]:
    z3_label = "SAFE" if z3_safe else "UNSAFE"
    if runtime_label not in ("SAFE", "UNSAFE"):
        interpretation = "not_comparable"
    elif z3_label == "SAFE" and runtime_label == "SAFE":
        interpretation = "true_positive"
    elif z3_label == "SAFE" and runtime_label == "UNSAFE":
        interpretation = "formal_model_unsound"
    elif z3_label == "UNSAFE" and runtime_label == "SAFE":
        interpretation = "conservative_rejection"
    else:
        interpretation = "correct_rejection"
    return {"z3": z3_label, "runtime": runtime_label, "interpretation": interpretation}
