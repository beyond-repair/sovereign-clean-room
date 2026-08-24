#!/usr/bin/env python3
"""Stage-1 extraction tests — TaskAtom, Episode, MemSkill, CapabilityRegistry."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pytest

# Allow imports from core/
ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "core"
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

from episodic_memory import (  # noqa: E402
    Episode,
    EpisodicMemoryLedger,
    TaskAtom,
    GENESIS_HASH,
)
from memskill import (  # noqa: E402
    promote_memskill,
    validate_episode_for_promotion,
)
from capability_registry import (  # noqa: E402
    CapabilityDescriptor,
    CapabilityRegistry,
)


@pytest.fixture
def tmp_ledger(tmp_path: Path):
    return EpisodicMemoryLedger(tmp_path / "atoms")


def test_task_atom_immutable_and_hashed():
    a = TaskAtom.create("t1", "created", {"title": "hello"})
    assert a.atom_hash
    assert len(a.atom_hash) == 64
    with pytest.raises(Exception):
        # frozen dataclass
        a.task_id = "mutated"  # type: ignore[misc]


def test_task_atom_integrity_roundtrip():
    a = TaskAtom.create("t1", "created", {"title": "x"})
    d = a.to_dict()
    b = TaskAtom.from_dict(d)
    assert b.atom_hash == a.atom_hash
    d["payload"] = {"title": "tampered"}
    with pytest.raises(ValueError, match="integrity"):
        TaskAtom.from_dict(d)


def test_append_only_chain(tmp_ledger: EpisodicMemoryLedger):
    a1 = tmp_ledger.create_and_append("task-a", "created", {"title": "One"})
    assert a1.prev_atom_hash == GENESIS_HASH
    a2 = tmp_ledger.create_and_append("task-a", "assigned", {"agent": "local"})
    assert a2.prev_atom_hash == a1.atom_hash
    a3 = tmp_ledger.create_and_append("task-a", "completed", {"result": "ok"})
    assert a3.prev_atom_hash == a2.atom_hash
    v = tmp_ledger.verify_chain()
    assert v["ok"] is True
    assert v["count"] == 3


def test_prev_hash_mismatch_rejected(tmp_ledger: EpisodicMemoryLedger):
    tmp_ledger.create_and_append("t", "created", {})
    bad = TaskAtom.create("t", "completed", {}, prev_atom_hash=GENESIS_HASH)
    with pytest.raises(ValueError, match="prev_atom_hash mismatch"):
        tmp_ledger.append(bad)


def test_episode_reconstruction(tmp_ledger: EpisodicMemoryLedger):
    tmp_ledger.create_and_append("ep1", "created", {"title": "Build", "description": "wall"})
    tmp_ledger.create_and_append("ep1", "completed", {"result": "done"})
    ep = tmp_ledger.reconstruct_episode("ep1")
    assert isinstance(ep, Episode)
    assert ep.terminal_status == "completed"
    assert ep.title == "Build"
    assert "Build" in ep.content_summary()


def test_promote_memskill_success(tmp_ledger: EpisodicMemoryLedger):
    tmp_ledger.create_and_append("p1", "created", {"title": "Skill candidate", "description": "learn"})
    tmp_ledger.create_and_append("p1", "completed", {})
    ep = tmp_ledger.reconstruct_episode("p1")
    pkg = promote_memskill(ep)
    assert pkg["manifest"]["skill_id"].startswith("memskill_")
    assert pkg["manifest"]["network_access"] is False
    assert pkg["manifest"]["source_task_id"] == "p1"


def test_promote_rejects_open_episode(tmp_ledger: EpisodicMemoryLedger):
    tmp_ledger.create_and_append("open1", "created", {"title": "Open"})
    ep = tmp_ledger.reconstruct_episode("open1")
    with pytest.raises(ValueError, match="completed"):
        validate_episode_for_promotion(ep)


def test_capability_registry_denies_network(tmp_path: Path):
    reg = CapabilityRegistry(tmp_path / "caps")
    with pytest.raises(PermissionError):
        reg.register(
            CapabilityDescriptor(
                capability_id="evil",
                name="evil",
                description="n",
                network_access=True,
            )
        )


def test_capability_registry_from_package(tmp_path: Path, tmp_ledger: EpisodicMemoryLedger):
    tmp_ledger.create_and_append("r1", "created", {"title": "Reg", "description": "d"})
    tmp_ledger.create_and_append("r1", "completed", {})
    ep = tmp_ledger.reconstruct_episode("r1")
    reg = CapabilityRegistry(tmp_path / "caps")
    pkg = promote_memskill(ep, registry=reg)
    assert reg.lookup_skill(pkg["manifest"]["skill_id"]) is not None
    caps = reg.list_capabilities()
    assert len(caps) == 1
    assert caps[0].network_access is False


def test_registry_persist_reload(tmp_path: Path):
    root = tmp_path / "caps"
    reg = CapabilityRegistry(root)
    reg.register(
        CapabilityDescriptor(
            capability_id="c1",
            name="n1",
            description="d1",
        )
    )
    reg2 = CapabilityRegistry(root)
    assert reg2.get("c1") is not None
    assert reg2.get("c1").name == "n1"
