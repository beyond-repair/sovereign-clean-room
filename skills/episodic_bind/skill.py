#!/usr/bin/env python3
"""
Gated skill: episodic_bind v1.0.0

Offline-only. Binds a local note filler to the EPISODIC role using FHRR,
checks invertibility against the constitutional gate, and touches SUCCESS/FAILURE.

Never opens network sockets. Never writes outside the engine codebook
unless the caller persists state via CleanRoomVSAEngine.save().
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Optional, TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from clean_room_vsa import CleanRoomVSAEngine, CleanRoomGate

PACKAGE_DIR = Path(__file__).resolve().parent
PACKAGE_JSON = PACKAGE_DIR / "package.json"

REQUIRED_ATOMS = (
    "SELF",
    "ENVIRONMENT",
    "EPISODIC",
    "SEMANTIC",
    "SUCCESS",
    "FAILURE",
)


def load_package_manifest() -> Dict[str, Any]:
    with open(PACKAGE_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_sovereignty(pkg: Dict[str, Any]) -> None:
    sov = pkg["sovereignty"]
    if sov.get("network_access") is not False:
        raise PermissionError("episodic_bind requires network_access=false")
    if sov.get("file_system_access") not in ("none", "read_only", "isolated_temp"):
        raise PermissionError("invalid file_system_access")
    if pkg["vsa_bindings"]["dimension"] != 8192:
        raise ValueError("dimension must be 8192")
    if pkg["vsa_bindings"]["binding_threshold"] < 0.92:
        raise ValueError("binding_threshold must be >= 0.92")


def note_to_filler(engine: "CleanRoomVSAEngine", note: str) -> np.ndarray:
    """
    Deterministic FHRR filler from local note text.
    Hash → seeded phase vector on the unit hypersphere (no network, no disk).
    """
    digest = hashlib.sha256(note.encode("utf-8")).digest()
    seed = int.from_bytes(digest[:8], "big") % (2**32 - 1)
    rng = np.random.default_rng(seed)
    return engine.random_symbol(rng=rng)


def ensure_jump_start(engine: "CleanRoomVSAEngine") -> None:
    missing = [a for a in REQUIRED_ATOMS if a not in engine.codebook]
    if missing:
        raise RuntimeError(
            f"Jump-Start primitives missing: {missing}. Run jump_start_v01() first."
        )
    if not engine.verify_jump_start_integrity():
        raise RuntimeError("Jump-Start integrity failed")


def run_episodic_bind(
    engine: "CleanRoomVSAEngine",
    note: str,
    require_jump_start: bool = True,
    register_bound: bool = True,
) -> Dict[str, Any]:
    """
    Core skill body (pure local VSA).

    1. Load EPISODIC role from codebook
    2. Build deterministic filler from note
    3. Bind role ⊙ filler
    4. Unbind and score invertibility
    5. Touch SUCCESS or FAILURE atom
    """
    pkg = load_package_manifest()
    validate_sovereignty(pkg)
    threshold = float(pkg["vsa_bindings"]["binding_threshold"])

    if require_jump_start:
        ensure_jump_start(engine)

    if not isinstance(note, str) or not note.strip():
        engine.touch("FAILURE")
        return {
            "status": "FAIL",
            "invertibility": 0.0,
            "bound_atom": None,
            "evidence": "FAILURE",
            "error": "note must be a non-empty string",
        }

    role = engine.codebook["EPISODIC"]
    filler = note_to_filler(engine, note.strip())
    bound = engine.bind(role, filler)
    recovered = engine.unbind(bound, role)
    score = engine.similarity(filler, recovered)

    if score >= threshold:
        engine.touch("SUCCESS")
        atom_name = None
        if register_bound:
            # Ephemeral skill trace name — not a Jump-Start atom
            safe = hashlib.sha256(note.encode("utf-8")).hexdigest()[:12]
            atom_name = f"episodic_note_{safe}"
            engine.register(atom_name, bound, pinned=False)
        return {
            "status": "PASS",
            "invertibility": score,
            "bound_atom": atom_name,
            "evidence": "SUCCESS",
            "error": None,
        }

    engine.touch("FAILURE")
    return {
        "status": "FAIL",
        "invertibility": score,
        "bound_atom": None,
        "evidence": "FAILURE",
        "error": f"invertibility {score:.6f} < threshold {threshold}",
    }


def run_via_gate(
    gate: "CleanRoomGate",
    note: str,
    require_jump_start: bool = True,
) -> Dict[str, Any]:
    """Execute skill body inside CleanRoomGate (sanitized PASS/FAIL)."""

    def _payload():
        return run_episodic_bind(
            gate.vsa,
            note=note,
            require_jump_start=require_jump_start,
        )

    return gate.execute_sandboxed_computation("episodic_bind", _payload)
