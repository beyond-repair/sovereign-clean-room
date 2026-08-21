#!/usr/bin/env python3
"""
Ware Constant Physics & SPARC Data Bridge — offline only.

Models phenomenological rotation-curve residuals using the repository Ware
recursion and a simplified Proca / coherence coupling term. Bundled sample
curves stand in for SPARC tables when no local CSV is provided.

Does NOT claim experimental confirmation of vacuum-energy extraction or
propulsion. Outputs are numerical comparisons + FHRR encodings for the
sovereign agent stack.

network_access: false
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np

from clean_room_vsa import CleanRoomVSAEngine
from clean_room_ledger import CleanRoomLedger
from clean_room_shacl import LocalGraph, ShapeEngine, ValidationReport

# Repository-aligned Ware recursion (engineering-normalized)
W0 = 0.08
XI = 0.23  # ξ
N_REF = 3


def ware_weight(n: float) -> float:
    """W(n) = 0.08 * exp(0.23 * (n - 3))."""
    return float(W0 * math.exp(XI * (n - N_REF)))


def ghost_free(n: float, bound: float = 0.125) -> bool:
    return ware_weight(n) < bound


# ---------------------------------------------------------------------------
# Bundled SPARC-like sample (synthetic but structured like R, Vobs, Vgas, Vdisk)
# Units: R [kpc], V [km/s]
# ---------------------------------------------------------------------------

SAMPLE_GALAXIES: Dict[str, List[Dict[str, float]]] = {
    "SAMPLE_A": [
        {"R": 0.5, "Vobs": 45.0, "Vgas": 10.0, "Vdisk": 40.0},
        {"R": 1.0, "Vobs": 70.0, "Vgas": 15.0, "Vdisk": 60.0},
        {"R": 2.0, "Vobs": 95.0, "Vgas": 20.0, "Vdisk": 75.0},
        {"R": 4.0, "Vobs": 110.0, "Vgas": 22.0, "Vdisk": 80.0},
        {"R": 8.0, "Vobs": 118.0, "Vgas": 20.0, "Vdisk": 78.0},
        {"R": 12.0, "Vobs": 120.0, "Vgas": 18.0, "Vdisk": 72.0},
    ],
    "SAMPLE_B": [
        {"R": 0.8, "Vobs": 30.0, "Vgas": 8.0, "Vdisk": 25.0},
        {"R": 1.5, "Vobs": 50.0, "Vgas": 12.0, "Vdisk": 40.0},
        {"R": 3.0, "Vobs": 75.0, "Vgas": 18.0, "Vdisk": 55.0},
        {"R": 6.0, "Vobs": 90.0, "Vgas": 20.0, "Vdisk": 58.0},
        {"R": 10.0, "Vobs": 95.0, "Vgas": 16.0, "Vdisk": 55.0},
    ],
}


PHYSICS_SHAPES: Dict[str, Any] = {
    "shapes": [
        {
            "id": "PhysicsRunShape",
            "targetClass": "seem:PhysicsRun",
            "closed": False,
            "properties": [
                {
                    "path": "seem:network_access",
                    "minCount": 1,
                    "hasValue": False,
                },
                {
                    "path": "seem:status",
                    "minCount": 1,
                    "in": ["PASS", "FAIL", "INCONCLUSIVE"],
                },
                {
                    "path": "seem:ghost_free",
                    "datatype": "boolean",
                    "minCount": 1,
                },
            ],
        }
    ]
}


@dataclass
class CurvePoint:
    R: float
    Vobs: float
    Vgas: float = 0.0
    Vdisk: float = 0.0
    Vbulge: float = 0.0


@dataclass
class FitResult:
    galaxy_id: str
    n: float
    W_n: float
    ghost_free: bool
    chi2_newton: float
    chi2_ware: float
    rms_newton: float
    rms_ware: float
    improvement: float  # (chi2_n - chi2_w) / max(chi2_n, 1e-12)
    points: int
    network_access: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "galaxy_id": self.galaxy_id,
            "n": self.n,
            "W_n": self.W_n,
            "ghost_free": self.ghost_free,
            "chi2_newton": self.chi2_newton,
            "chi2_ware": self.chi2_ware,
            "rms_newton": self.rms_newton,
            "rms_ware": self.rms_ware,
            "improvement": self.improvement,
            "points": self.points,
            "network_access": False,
        }


def load_sparc_csv(path: Path) -> List[CurvePoint]:
    """Load local SPARC-style CSV with columns R,Vobs[,Vgas,Vdisk,Vbulge]."""
    points: List[CurvePoint] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            points.append(
                CurvePoint(
                    R=float(row["R"]),
                    Vobs=float(row["Vobs"]),
                    Vgas=float(row.get("Vgas") or 0.0),
                    Vdisk=float(row.get("Vdisk") or 0.0),
                    Vbulge=float(row.get("Vbulge") or 0.0),
                )
            )
    if not points:
        raise ValueError(f"empty curve file: {path}")
    return points


def sample_galaxy(galaxy_id: str = "SAMPLE_A") -> List[CurvePoint]:
    raw = SAMPLE_GALAXIES.get(galaxy_id)
    if not raw:
        raise KeyError(f"unknown sample galaxy: {galaxy_id}")
    return [CurvePoint(**row) for row in raw]


def baryonic_speed(p: CurvePoint) -> float:
    """V_bar^2 = Vgas^2 + Vdisk^2 + Vbulge^2 (simple quadrature)."""
    return math.sqrt(max(0.0, p.Vgas**2 + p.Vdisk**2 + p.Vbulge**2))


def newtonian_model(p: CurvePoint) -> float:
    return baryonic_speed(p)


def proca_coherence_term(R: float, n: float, kappa: float = 25.0) -> float:
    """
    Phenomenological outer-rise term inspired by ultra-light vector/coherence
    coupling: δV ∝ W(n) * κ * R / (1 + R).

    Not a derivation of vacuum extraction — a local fitting ansatz only.
    """
    W = ware_weight(n)
    return W * kappa * (R / (1.0 + R))


def ware_model(p: CurvePoint, n: float, kappa: float = 25.0) -> float:
    v_b = baryonic_speed(p)
    delta = proca_coherence_term(p.R, n, kappa=kappa)
    return math.sqrt(max(0.0, v_b**2 + delta**2))


def chi2_rms(
    points: Sequence[CurvePoint],
    model_fn,
) -> Tuple[float, float]:
    errs = []
    for p in points:
        pred = model_fn(p)
        errs.append(p.Vobs - pred)
    arr = np.asarray(errs, dtype=np.float64)
    chi2 = float(np.sum(arr**2))
    rms = float(np.sqrt(np.mean(arr**2))) if len(arr) else 0.0
    return chi2, rms


def fit_galaxy(
    points: Sequence[CurvePoint],
    galaxy_id: str,
    n: float = 3.0,
    kappa: float = 25.0,
) -> FitResult:
    chi2_n, rms_n = chi2_rms(points, newtonian_model)
    chi2_w, rms_w = chi2_rms(points, lambda p: ware_model(p, n, kappa=kappa))
    imp = (chi2_n - chi2_w) / max(chi2_n, 1e-12)
    return FitResult(
        galaxy_id=galaxy_id,
        n=float(n),
        W_n=ware_weight(n),
        ghost_free=ghost_free(n),
        chi2_newton=chi2_n,
        chi2_ware=chi2_w,
        rms_newton=rms_n,
        rms_ware=rms_w,
        improvement=float(imp),
        points=len(points),
    )


class WarePhysicsBridge:
    """Offline SPARC/Ware analysis + FHRR encoding + ledger."""

    def __init__(
        self,
        workspace: Optional[Union[str, Path]] = None,
        engine: Optional[CleanRoomVSAEngine] = None,
        ledger: Optional[CleanRoomLedger] = None,
    ):
        self.workspace = Path(workspace) if workspace else None
        self.engine = engine or CleanRoomVSAEngine(dim=8192)
        if self.engine.dim != 8192:
            raise ValueError("WarePhysicsBridge requires dim=8192")
        if not self.engine.verify_jump_start_integrity():
            self.engine.jump_start_v01()

        for name in ("WARE_CONSTANT", "SPARC_CURVE", "PHYSICS_PASS", "PHYSICS_FAIL"):
            if name not in self.engine.codebook:
                self.engine.register(name, pinned=True)

        if ledger is not None:
            self.ledger = ledger
        elif self.workspace is not None:
            self.ledger = CleanRoomLedger(self.workspace / "audit")
        else:
            self.ledger = None

        self.shapes = ShapeEngine(PHYSICS_SHAPES)

    def evaluate(
        self,
        galaxy_id: str = "SAMPLE_A",
        n: float = 3.0,
        kappa: float = 25.0,
        csv_path: Optional[Union[str, Path]] = None,
        log: bool = True,
    ) -> Dict[str, Any]:
        if csv_path:
            points = load_sparc_csv(Path(csv_path))
            gid = Path(csv_path).stem
        else:
            points = sample_galaxy(galaxy_id)
            gid = galaxy_id

        fit = fit_galaxy(points, gid, n=n, kappa=kappa)

        # Status: improvement and ghost-free — still INCONCLUSIVE physically
        if not fit.ghost_free:
            status = "FAIL"
        elif fit.improvement > 0.05:
            status = "PASS"  # phenomenological fit better; not physics proof
        elif fit.improvement < -0.05:
            status = "FAIL"
        else:
            status = "INCONCLUSIVE"

        report = self._shacl_run(status, fit.ghost_free)
        vec_name = self._encode_fit(fit, status)

        out = {
            "status": status,
            "fit": fit.to_dict(),
            "shacl_conforms": report.conforms,
            "fhrr_atom": vec_name,
            "network_access": False,
            "disclaimer": (
                "Offline phenomenological comparison only; "
                "not experimental proof of vacuum extraction or modified gravity."
            ),
        }

        if log and self.ledger is not None:
            entry = self.ledger.append("physics_ware_sparc", out)
            out["ledger_seq"] = entry.seq
            out["ledger_hash"] = entry.entry_hash

        return out

    def _encode_fit(self, fit: FitResult, status: str) -> str:
        role = self.engine.codebook["WARE_CONSTANT"]
        flag = (
            self.engine.codebook["PHYSICS_PASS"]
            if status == "PASS"
            else self.engine.codebook["PHYSICS_FAIL"]
        )
        # Mix in a content hash of residual metrics for uniqueness
        digest = hashlib.sha256(
            json.dumps(fit.to_dict(), sort_keys=True).encode("utf-8")
        ).digest()
        seed = int.from_bytes(digest[:8], "big") % (2**32 - 1)
        rng = np.random.default_rng(seed)
        filler = self.engine.random_symbol(rng=rng)
        bound = self.engine.bind(role, self.engine.bind(flag, filler))
        name = f"PHYS::{fit.galaxy_id}::n{fit.n}"
        self.engine.register(name, bound, pinned=False)
        return name

    def _shacl_run(self, status: str, ghost_free_flag: bool) -> ValidationReport:
        g = LocalGraph()
        g.add("run:1", "rdf:type", "seem:PhysicsRun")
        g.add("run:1", "seem:status", status)
        g.add("run:1", "seem:network_access", False)
        g.add("run:1", "seem:ghost_free", bool(ghost_free_flag))
        return self.shapes.validate_graph(g, shape_id="PhysicsRunShape")


def physics_skill_handler(bridge: WarePhysicsBridge):
    """Orchestrator handler: state inputs → Ware/SPARC evaluation."""

    def handler(engine, gate, state, idx):
        inputs = state.get("inputs") if isinstance(state.get("inputs"), dict) else {}
        galaxy = state.get("galaxy_id") or inputs.get("galaxy_id") or "SAMPLE_A"
        n = float(state.get("n") or inputs.get("n") or 3.0)
        kappa = float(state.get("kappa") or inputs.get("kappa") or 25.0)
        csv_path = state.get("csv_path") or inputs.get("csv_path")
        result = bridge.evaluate(
            galaxy_id=str(galaxy),
            n=n,
            kappa=kappa,
            csv_path=csv_path,
            log=True,
        )
        state.setdefault("telemetry", {})["physics_status"] = result["status"]
        state["telemetry"]["W_n"] = result["fit"]["W_n"]
        return result

    return handler
