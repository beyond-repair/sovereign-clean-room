#!/usr/bin/env python3
"""Export AttestationBundle v0.1 from a physics result JSON (offline)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))

from clean_room_attestation import export_physics_attestation  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description="Export Clean-Room attestation (offline)")
    p.add_argument("--from-physics-json", required=True, help="Path to physics result JSON")
    p.add_argument("-o", "--output", default="attestation.json")
    p.add_argument("--workspace-id", default="local")
    args = p.parse_args()

    src = Path(args.from_physics_json)
    if not src.is_file():
        print(f"not found: {src}", file=sys.stderr)
        return 1
    data = json.loads(src.read_text(encoding="utf-8"))
    out = Path(args.output)
    bundle = export_physics_attestation(
        data, out, workspace_id=args.workspace_id
    )
    print(json.dumps({"ok": True, "path": str(out), "schema": bundle.schema}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
