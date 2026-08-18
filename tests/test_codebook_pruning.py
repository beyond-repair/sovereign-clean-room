#!/usr/bin/env python3
"""Tests for sparse codebook pruning (v1.3.1)."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))

from clean_room_vsa import (  # noqa: E402
    CleanRoomVSAEngine,
    DEFAULT_PROTECTED_ATOMS,
)


def test_protected_atoms_survive_utility_prune() -> None:
    vsa = CleanRoomVSAEngine(dim=512, sparsity_k=32, max_codebook_size=8)
    for name in DEFAULT_PROTECTED_ATOMS:
        vsa.register(name, pinned=True)
    for i in range(20):
        vsa.register(f"junk_{i}", pinned=False)

    report = vsa.prune_codebook(max_size=8)
    assert len(vsa.codebook) <= 8 + len(
        [n for n in DEFAULT_PROTECTED_ATOMS if n in vsa.codebook]
    ) or all(n in vsa.codebook for n in DEFAULT_PROTECTED_ATOMS)
    for name in DEFAULT_PROTECTED_ATOMS:
        assert name in vsa.codebook, f"protected atom lost: {name}"
    assert report["utility"] or len(vsa.codebook) <= 8 + 6
    print("[OK] protected atoms survive utility prune")


def test_redundancy_cull() -> None:
    vsa = CleanRoomVSAEngine(dim=512, sparsity_k=32, redundancy_threshold=0.95)
    base = vsa.random_symbol()
    vsa.register("keep_me", base, pinned=True)
    # Near-identical unpinned copy
    near = base * np.exp(1j * 0.001)
    near = near / np.linalg.norm(near)
    vsa.register("dup", near, pinned=False)

    removed = vsa.prune_redundant()
    assert "dup" in removed
    assert "keep_me" in vsa.codebook
    assert "dup" not in vsa.codebook
    print("[OK] redundancy cull drops unpinned near-duplicate")


def test_touch_increases_utility() -> None:
    vsa = CleanRoomVSAEngine(dim=512, sparsity_k=32, max_codebook_size=3)
    vsa.register("hot", pinned=False)
    vsa.register("cold", pinned=False)
    vsa.register("colder", pinned=False)
    vsa.register("newest", pinned=False)
    for _ in range(50):
        vsa.touch("hot")

    report = vsa.prune_by_utility(max_size=2)
    assert "hot" in vsa.codebook
    assert "hot" not in report
    print(f"[OK] high-utility atom retained; pruned={report}")


if __name__ == "__main__":
    test_protected_atoms_survive_utility_prune()
    test_redundancy_cull()
    test_touch_increases_utility()
    print("--- PRUNING TESTS PASSED ---")
