#!/usr/bin/env python3
"""Sign a skill package.json with a local Ed25519 signing key (offline)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))

from skill_crypto import sign_package  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Sign SEEM skill package.json")
    parser.add_argument("package", type=Path, help="Path to package.json")
    parser.add_argument(
        "--signing-key",
        type=Path,
        required=True,
        help="Path to hex signing key file (*.sk)",
    )
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Overwrite package.json with signed version",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Write signed package to this path",
    )
    args = parser.parse_args()

    pkg = json.loads(args.package.read_text(encoding="utf-8"))
    if pkg.get("sovereignty", {}).get("network_access") is not False:
        print("[-] Refusing to sign package with network_access != false")
        return 1

    sk_hex = args.signing_key.read_text(encoding="utf-8").strip().split()[0]
    signed = sign_package(pkg, sk_hex)

    out = args.output
    if args.in_place:
        out = args.package
    if out is None:
        out = args.package.with_name(args.package.stem + ".signed.json")

    out.write_text(json.dumps(signed, indent=2) + "\n", encoding="utf-8")
    print(f"[+] Signed → {out}")
    print(f"[+] signature={signed['manifest']['signature'][:16]}…")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
