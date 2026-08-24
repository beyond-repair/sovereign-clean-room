#!/usr/bin/env python3
"""Clean-Room VSA core — base64 assembled for CI restore."""
import base64
from pathlib import Path
_b64 = "".join(
    (Path(__file__).resolve().parent / f"_vsa_b64_{i}.txt").read_text(encoding="ascii")
    for i in range(5)
)
exec(base64.b64decode(_b64).decode("utf-8"), globals())
