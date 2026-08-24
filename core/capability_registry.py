#!/usr/bin/env python3
"""
Offline Capability Registry for Sovereign Clean-Room.

# Extracted 2026-08-24
# Source: beyond-repair/Gia---General-Intelligence-Assistant
# Files: base_agent.py, workflow.py, workflow_engine.py, task_processor.py
# Pattern: capability declaration / tool registration / workflow metadata
# Discarded: all network, GitHub, LLM, remote execution code

Integrates with CleanRoomGate conceptually (network_access always denied).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


@dataclass(frozen=True)
class CapabilityDescriptor:
    """Pure metadata — no executable code, no network."""

    capability_id: str
    name: str
    description: str
    version: str = "1.0.0"
    network_access: bool = False
    inputs_schema: Dict[str, Any] = field(default_factory=dict)
    outputs_schema: Dict[str, Any] = field(default_factory=dict)
    source_skill_id: Optional[str] = None
    registered_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "capability_id": self.capability_id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "network_access": False,  # forced
            "inputs_schema": dict(self.inputs_schema),
            "outputs_schema": dict(self.outputs_schema),
            "source_skill_id": self.source_skill_id,
            "registered_at": self.registered_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CapabilityDescriptor":
        if d.get("network_access") is True:
            raise PermissionError("capabilities requesting network_access are rejected")
        return cls(
            capability_id=str(d["capability_id"]),
            name=str(d.get("name", d["capability_id"])),
            description=str(d.get("description", "")),
            version=str(d.get("version", "1.0.0")),
            network_access=False,
            inputs_schema=dict(d.get("inputs_schema") or {}),
            outputs_schema=dict(d.get("outputs_schema") or {}),
            source_skill_id=d.get("source_skill_id"),
            registered_at=float(d.get("registered_at", time.time())),
        )


@dataclass(frozen=True)
class SkillManifest:
    """Lightweight skill identity for registry lookup."""

    skill_id: str
    title: str
    content_hash: str
    network_access: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "title": self.title,
            "content_hash": self.content_hash,
            "network_access": False,
        }


class CapabilityRegistry:
    """
    Register / lookup capability metadata.
    Denies any manifest that requests network_access.
    Persist to local JSON only.
    """

    def __init__(self, root: Union[str, Path]):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "capabilities.json"
        self._caps: Dict[str, CapabilityDescriptor] = {}
        self._skills: Dict[str, SkillManifest] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.is_file():
            return
        data = json.loads(self.path.read_text(encoding="utf-8"))
        for raw in data.get("capabilities", []):
            try:
                cap = CapabilityDescriptor.from_dict(raw)
                self._caps[cap.capability_id] = cap
            except PermissionError:
                continue  # skip illegal entries
        for raw in data.get("skills", []):
            sid = str(raw.get("skill_id", ""))
            if not sid:
                continue
            if raw.get("network_access") is True:
                continue
            self._skills[sid] = SkillManifest(
                skill_id=sid,
                title=str(raw.get("title", sid)),
                content_hash=str(raw.get("content_hash", "")),
                network_access=False,
            )

    def _save(self) -> None:
        body = {
            "version": "capability_registry_v1",
            "capabilities": [c.to_dict() for c in self._caps.values()],
            "skills": [s.to_dict() for s in self._skills.values()],
        }
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(body, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(self.path)

    def register(self, descriptor: CapabilityDescriptor) -> None:
        if descriptor.network_access:
            raise PermissionError("network_access capabilities are forbidden")
        self._caps[descriptor.capability_id] = descriptor
        self._save()

    def register_from_package(self, package: Dict[str, Any]) -> CapabilityDescriptor:
        """Ingest a MemSkill / skill package manifest."""
        m = package.get("manifest") or {}
        if m.get("network_access") is True:
            raise PermissionError("package requests network_access — rejected")
        skill_id = str(m.get("skill_id") or m.get("id") or "")
        if not skill_id:
            raise ValueError("package.manifest.skill_id required")
        cap = CapabilityDescriptor(
            capability_id=f"cap_{skill_id}",
            name=str(m.get("title") or skill_id),
            description=str(m.get("description") or ""),
            version=str(m.get("version", "1.0.0")),
            network_access=False,
            source_skill_id=skill_id,
        )
        self.register(cap)
        self._skills[skill_id] = SkillManifest(
            skill_id=skill_id,
            title=cap.name,
            content_hash=str(m.get("content_hash", "")),
            network_access=False,
        )
        self._save()
        return cap

    def get(self, capability_id: str) -> Optional[CapabilityDescriptor]:
        return self._caps.get(capability_id)

    def lookup_skill(self, skill_id: str) -> Optional[SkillManifest]:
        return self._skills.get(skill_id)

    def list_capabilities(self) -> List[CapabilityDescriptor]:
        return list(self._caps.values())

    def reject_network_request(self, manifest: Dict[str, Any]) -> None:
        """Explicit gate used by orchestrator / CleanRoomGate."""
        if manifest.get("network_access") is True:
            raise PermissionError("CleanRoomGate: network_access denied")
