#!/usr/bin/env python3
"""
MemSkill promotion — Episode → signed offline skill package.

# Extracted 2026-08-24
# Source: beyond-repair/My-mind-A.I.
# Files: gpt_agent.py, main.py
# Pattern: completed work → permanent, auditable capability (rewritten without LLM)

Uses existing skill_crypto (Ed25519) and CapabilityRegistry.
No network, no external model calls.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from episodic_memory import Episode, TaskAtom

try:
    from skill_crypto import (
        canonical_package_bytes,
        is_placeholder_signature,
        sign_package,
        verify_package,
    )
except ImportError:  # pragma: no cover
    sign_package = None  # type: ignore
    verify_package = None  # type: ignore
    is_placeholder_signature = lambda s: True  # type: ignore


@dataclass(frozen=True)
class SkillPackage:
    """Deterministic, signable skill artefact derived from an Episode."""

    skill_id: str
    source_task_id: str
    title: str
    description: str
    content_hash: str
    atoms_summary: List[Dict[str, Any]]
    created_at: float
    network_access: bool = False  # always False in clean-room

    def to_manifest(self) -> Dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "source_task_id": self.source_task_id,
            "title": self.title,
            "description": self.description,
            "content_hash": self.content_hash,
            "atoms_summary": self.atoms_summary,
            "created_at": self.created_at,
            "network_access": False,
            "signature": "",
        }

    def to_package(self) -> Dict[str, Any]:
        return {"manifest": self.to_manifest(), "body": {"kind": "memskill_v1"}}


def _content_hash(episode: Episode) -> str:
    return hashlib.sha256(episode.content_summary().encode("utf-8")).hexdigest()


def _skill_id(episode: Episode) -> str:
    h = _content_hash(episode)
    return f"memskill_{episode.task_id[:8]}_{h[:12]}"


def validate_episode_for_promotion(episode: Episode) -> None:
    """Reject incomplete or empty episodes."""
    if not episode.atoms:
        raise ValueError("cannot promote empty episode")
    if episode.terminal_status not in ("completed",):
        raise ValueError(
            f"only completed episodes may be promoted (got {episode.terminal_status})"
        )
    if not episode.title and not episode.description:
        # still allow if atoms carry payload
        if not any(a.payload for a in episode.atoms):
            raise ValueError("episode has no meaningful content")


def promote_memskill(
    episode: Episode,
    signing_key_hex: Optional[str] = None,
    registry: Any = None,
) -> Dict[str, Any]:
    """
    Episode → Validation → (optional) Signature → Skill Package → Registry entry.

    Returns the signed (or unsigned-dev) package dict.
    network_access is forced False.
    """
    validate_episode_for_promotion(episode)

    atoms_summary = [
        {
            "atom_id": a.atom_id,
            "event_type": a.event_type,
            "atom_hash": a.atom_hash,
        }
        for a in episode.atoms
    ]
    pkg_obj = SkillPackage(
        skill_id=_skill_id(episode),
        source_task_id=episode.task_id,
        title=episode.title or episode.task_id,
        description=episode.description or episode.content_summary()[:500],
        content_hash=_content_hash(episode),
        atoms_summary=atoms_summary,
        created_at=time.time(),
        network_access=False,
    )
    package = pkg_obj.to_package()

    if signing_key_hex and sign_package is not None:
        package = sign_package(package, signing_key_hex)
    else:
        package["manifest"]["signature"] = "UNSIGNED_DEV_PLACEHOLDER"

    if registry is not None:
        registry.register_from_package(package)

    return package


def verify_memskill_package(
    package: Dict[str, Any],
    trusted_verify_keys_hex: Optional[List[str]] = None,
) -> bool:
    """Verify signature if keys provided; always enforce network_access=False."""
    manifest = package.get("manifest") or {}
    if manifest.get("network_access") is True:
        raise PermissionError("MemSkill packages must not request network_access")
    sig = manifest.get("signature")
    if is_placeholder_signature(sig):
        return False  # unsigned is not production-valid
    if not trusted_verify_keys_hex or verify_package is None:
        raise PermissionError("no trusted keys for MemSkill verification")
    return verify_package(package, trusted_verify_keys_hex)
