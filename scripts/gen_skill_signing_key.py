#!/usr/bin/env python3
"""Generate a local Ed25519 keypair for signing gated skill packages (offline)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))

from skill_crypto import generate_keypair, save_keypair  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="SEEM offline skill signing keygen")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "keys",
        help="Directory for .sk / .pub (default: ./keys)",
    )
    parser.add_argument("--name", default="skill_root", help="Key basename")
    args = parser.parse_args()

    sk_hex, vk_hex = generate_keypair()
    paths = save_keypair(args.out_dir, sk_hex, vk_hex, name=args.name)
    print(f"[+] Signing key (PRIVATE): {paths['signing_key']}")
    print(f"[+] Verify key (PUBLIC):  {paths['verify_key']}")
    print("[!] Never commit *.sk files. Commit *.pub only if you intend a public trust root.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
