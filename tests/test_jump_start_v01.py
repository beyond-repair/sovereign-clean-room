#!/usr/bin/env python3
"""Jump-Start v0.1 tests against CleanRoomVSAEngine (FHRR)."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))

from clean_room_vsa import CleanRoomVSAEngine, DEFAULT_PROTECTED_ATOMS  # noqa: E402

SEED = 0x5345454D


def test_jump_start_registers_six_pinned() -> None:
    vsa = CleanRoomVSAEngine(dim=8192)
    manifest = vsa.jump_start_v01(seed=SEED)
    assert set(manifest["atoms"]) == DEFAULT_PROTECTED_ATOMS
    assert manifest["all_pinned"] is True
    assert vsa.verify_jump_start_integrity()
    for name in DEFAULT_PROTECTED_ATOMS:
        assert vsa.atom_meta[name]["pinned"] is True
        nrm = float(abs((__import__("numpy").linalg.norm(vsa.codebook[name]))))
        assert abs(nrm - 1.0) < 1e-9
    print("[OK] six pinned primitives registered")


def test_jump_start_deterministic_seed() -> None:
    a = CleanRoomVSAEngine(dim=512)
    b = CleanRoomVSAEngine(dim=512)
    a.jump_start_v01(seed=SEED)
    b.jump_start_v01(seed=SEED)
    for name in DEFAULT_PROTECTED_ATOMS:
        sim = a.similarity(a.codebook[name], b.codebook[name])
        assert sim > 0.999999, name
    print("[OK] deterministic seed reproduces vectors")


def test_jump_start_save_load_fidelity() -> None:
    vsa = CleanRoomVSAEngine(dim=8192)
    vsa.jump_start_v01(seed=SEED)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "state"
        vsa.save(path)
        other = CleanRoomVSAEngine()
        other.load(path)
        assert other.verify_jump_start_integrity()
        for name in DEFAULT_PROTECTED_ATOMS:
            sim = other.similarity(vsa.codebook[name], other.codebook[name])
            assert sim > 0.999999, f"{name} sim={sim}"
    print("[OK] save/load preserves Jump-Start vectors")


def test_jump_start_survives_prune() -> None:
    vsa = CleanRoomVSAEngine(dim=512, max_codebook_size=6)
    vsa.jump_start_v01(seed=123)
    for i in range(30):
        vsa.register(f"noise_{i}", pinned=False)
    vsa.prune_codebook(max_size=6)
    assert vsa.verify_jump_start_integrity()
    print("[OK] Jump-Start atoms survive aggressive prune")


if __name__ == "__main__":
    test_jump_start_registers_six_pinned()
    test_jump_start_deterministic_seed()
    test_jump_start_save_load_fidelity()
    test_jump_start_survives_prune()
    print("--- JUMP-START v0.1 TESTS PASSED ---")
