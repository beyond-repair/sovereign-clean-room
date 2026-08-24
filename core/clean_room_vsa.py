#!/usr/bin/env python3
"""Clean-Room VSA core — assembled from part files for CI restore."""
from pathlib import Path
_code = "".join(
    (Path(__file__).resolve().parent / f"_vsa_part_{i}.py").read_text(encoding="utf-8")
    for i in range(6)
)
exec(_code, globals())
