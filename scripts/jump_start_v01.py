#!/usr/bin/env python3
"""
Jump-Start v0.1 — bootstrap a twin on the constitutional Clean-Room substrate.

Uses FHRR complex unit-hypersphere vectors (v1.3.1), NOT bipolar embeddings.
Primitives (locked): SELF, ENVIRONMENT, EPISODIC, SEMANTIC, SUCCESS, FAILURE
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))

from clean_room_vsa import CleanRoomVSAEngine, DEFAULT_PROTECTED_ATOMS  # noqa: E402

# SEEM ASCII seed anchor (optional determinism for reproducible twins)
DEFAULT_SEED = 0x5345454D  # 'SEEM'


def main() -> int:
    parser = argparse.ArgumentParser(description="SEEM Jump-Start v0.1")
    parser.add_argument(
        "--state-dir",
        type=Path,
        default=Path("./twin_state_jumpstart_v01"),
        help="Directory for atomic twin state",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help="RNG seed for primitive vectors (default: SEEM ASCII)",
    )
    parser.add_argument(
        "--dim",
        type=int,
        default=8192,
        help="Must match constitution (8192)",
    )
    args = parser.parse_args()

    if args.dim != 8192:
        print(f"[!] Warning: constitution locks dim=8192; got {args.dim}")

    print("[*] Jump-Start v0.1 — initializing CleanRoomVSAEngine")
    vsa = CleanRoomVSAEngine(
        dim=args.dim,
        sparsity_k=256,
        iters=7,
        min_invertibility=0.92,
    )

    manifest = vsa.jump_start_v01(seed=args.seed)
    print(f"[+] Registered primitives: {manifest['atoms']}")
    print(f"[+] All pinned: {manifest['all_pinned']}")
    print(f"[+] Config: dim={manifest['dim']} sparsity_k={manifest['sparsity_k']} τ={manifest['min_invertibility']}")

    if not vsa.verify_jump_start_integrity():
        print("[-] Integrity failure before save")
        return 1

    args.state_dir.parent.mkdir(parents=True, exist_ok=True)
    print(f"[*] Saving state → {args.state_dir}")
    vsa.save(args.state_dir)

    print("[*] Reloading into fresh engine")
    restored = CleanRoomVSAEngine()
    restored.load(args.state_dir)

    if not restored.verify_jump_start_integrity():
        print("[-] Integrity failure after load")
        return 1

    # Vector fidelity: same names, unit norm, pinned
    for name in sorted(DEFAULT_PROTECTED_ATOMS):
        a = vsa.codebook[name]
        b = restored.codebook[name]
        sim = restored.similarity(a, b)
        if sim < 0.999999:
            print(f"[-] Vector drift on {name}: sim={sim}")
            return 1

    out = {
        "status": "PASS",
        "atoms": sorted(DEFAULT_PROTECTED_ATOMS),
        "state_dir": str(args.state_dir.resolve()),
        "seed": args.seed,
        "manifest": restored.jump_start_manifest(),
    }
    print(json.dumps(out, indent=2))
    print("[+] Jump-Start v0.1 complete — twin sealed for interaction history only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
