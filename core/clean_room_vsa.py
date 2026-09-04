#!/usr/bin/env python3
"""Clean-Room VSA core — Path A static module (LOADER_HARDENING).

Status: INCOMPLETE — full CleanRoomVSAEngine source is not present in this
repository. Prior base64 part-loader expected _vsa_b64_0..8; chunks 5–7 were
never uploaded; _vsa_part_0..2 contain only partial class fragments.

ADL-SEEM rule: Do not invent engine source.

Operator action required (see ADL-Governance OPERATOR_QUEUE.md):
  Path A (preferred): place a complete, reviewable clean_room_vsa.py (or
  core/vsa_engine.py + re-export) containing CleanRoomVSAEngine, CleanRoomGate,
  DEFAULT_PROTECTED_ATOMS, jump_start_v01, etc., then delete leftover
  _vsa_b64_*.txt and _vsa_part_*.py.
  Path B: exception-only dynamic load with signature + isolation (not used here).

Until restored, import fails closed so CI cannot silently claim maturity.
"""
from __future__ import annotations

# Explicit symbols other modules may try to import — keep names visible.
__all__ = [
    "CleanRoomVSAEngine",
    "CleanRoomGate",
    "DEFAULT_PROTECTED_ATOMS",
]

_MSG = (
    "CleanRoomVSAEngine source incomplete. "
    "Missing full static module (base64 chunks 5–7 never present; "
    "_vsa_part_0..2 are partial fragments only). "
    "Operator must restore per Path A in ADL-SEEM/docs/LOADER_HARDENING.md "
    "and ADL-Governance docs/OPERATOR_QUEUE.md. "
    "Do not invent engine source."
)


class _IncompleteVSA:
    """Placeholder so attribute access raises a clear, actionable error."""

    def __init__(self, *args, **kwargs):
        raise ImportError(_MSG)

    def __getattr__(self, name):
        raise ImportError(_MSG)


CleanRoomVSAEngine = _IncompleteVSA  # type: ignore[misc, assignment]
CleanRoomGate = _IncompleteVSA  # type: ignore[misc, assignment]
DEFAULT_PROTECTED_ATOMS = frozenset()  # empty until real engine restored


def __getattr__(name: str):
    # Any other historical symbol → same clear failure
    raise ImportError(_MSG)
