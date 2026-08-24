#!/usr/bin/env python3
"""
Sovereign Clean-Room VSA Core + BaNEL Integration Framework
(v1.3.3 — SHACL-aware Gate)

Complete production-grade implementation featuring:
- Single-pass unbind resonator loop with strict top-k cardinality
- Hyperspherical parallel-projection phase repulsion (BaNEL)
- Gated invertibility checks
- Sparse codebook pruning (utility + redundancy)
- Jump-Start v0.1 primitive registry
- Ed25519 skill package verification at the Clean-Room boundary
- Optional offline SHACL-subset constitutional validation
- Atomic disk persistence & sandboxed execution
"""

from __future__ import annotations
import numpy as np
from typing import Dict, List, Tuple, Optional, Callable, Any, Set, Iterable, Union
import time
import json
import shutil
from pathlib import Path


DEFAULT_PROTECTED_ATOMS: Set[str] = {
    "SELF",
    "ENVIRONMENT",
    "EPISODIC",
    "SEMANTIC",
    "SUCCESS",
    "FAILURE",
}

JUMP_START_V01_ATOMS: Tuple[str, ...] = (
    "SELF",
    "ENVIRONMENT",
    "EPISODIC",
    "SEMANTIC",
    "SUCCESS",
    "FAILURE",
)
