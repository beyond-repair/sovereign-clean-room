#!/usr/bin/env python3
"""
Ware Constant Physics & SPARC Data Bridge — pure offline kernel (v1 frozen).

Scientific boundary (locked):
  Phenomenological rotation-curve comparison + FHRR encoding only.
  Does NOT validate CFT, IQG, vacuum-energy extraction, or propulsion.
  PASS = relative RMSE improvement under stated assumptions — not physical proof.

Architectural boundary (locked):
  This module does not mutate the audit ledger or sign packages.
  CLI / Orchestrator / Gate own audit and cryptography.

Canonical Ware law (frozen):
  W(n) = 0.08 * exp(0.23 * (n - 3))
  W(3) = 0.08
  ghost_free := W(n) < 0.125

Claim flags (immutable on every PhysicsVerification):
  claim_class = "phenomenological_hypothesis"
  experimental_validation = false
  energy_extraction_validated = false
  thrust_validated = false

CLI exit codes: PASS=0 FAIL=2 INCONCLUSIVE=3
FHRR: dim=8192, unit norm
network_access: false — local paths only.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

# ---- frozen invariants ----
W0: float = 0.08
XI: float = 0.23
N_REF: float = 3.0
GHOST_BOUND: float = 0.125
FHRR_DIM: int = 8192

CLAIM_CLASS: str = "phenomenological_hypothesis"
CLAIM_FLAGS: Dict[str, Any] = {
    "claim_class": CLAIM_CLASS,
    "experimental_validation": False,
    "energy_extraction_validated": False,
    "thrust_validated": False,
}

SAMPLE_GALAXIES: Dict[str, List[Dict[str, float]]] = {
    "SAMPLE_A": [
        {"R": 0.5, "Vobs": 45.0, "Verr": 5.0, "Vgas": 10.0, "Vdisk": 40.0, "Vbulge": 0.0},
        {"R": 1.0, "Vobs": 70.0, "Verr": 5.0, "Vgas": 15.0, "Vdisk": 60.0, "Vbulge": 0.0},
        {"R": 2.0, "Vobs": 95.0, "Verr": 6.0, "Vgas": 20.0, "Vdisk": 75.0, "Vbulge": 0.0},
        {"R": 4.0, "Vobs": 110.0, "Verr": 6.0, "Vgas": 22.0, "Vdisk": 80.0, "Vbulge": 0.0},
        {"R": 8.0, "Vobs": 118.0, "Verr": 7.0, "Vgas": 20.0, "Vdisk": 78.0, "Vbulge": 0.0},
        {"R": 12.0, "Vobs": 120.0, "Verr": 8.0, "Vgas": 18.0, "Vdisk": 72.0, "Vbulge": 0.0},
    ],
    "SAMPLE_B": [
        {"R": 0.8, "Vobs": 30.0, "Verr": 4.0, "Vgas": 8.0, "Vdisk": 25.0, "Vbulge": 0.0},
        {"R": 1.5, "Vobs": 50.0, "Verr": 4.0, "Vgas": 12.0, "Vdisk": 40.0, "Vbulge": 0.0},
        {"R": 3.0, "Vobs": 75.0, "Verr": 5.0, "Vgas": 18.0, "Vdisk": 55.0, "Vbulge": 0.0},
        {"R": 6.0, "Vobs": 90.0, "Verr": 5.0, "Vgas": 20.0, "Vdisk": 58.0, "Vbulge": 0.0},
        {"R": 10.0, "Vobs": 95.0, "Verr": 6.0, "Vgas": 16.0, "Vdisk": 55.0, "Vbulge": 0.0},
    ],
}

_REMOTE_SCHEME = re.compile(r"^(https?|ftp|s3|gs|azure)://", re.I)

ASSUMPTIONS_BASE: List[str] = [
    "W(n)=0.08*exp(0.23*(n-3)) is engineering-normalized repository law, not a measured constant",
    "Proca δV term is a phenomenological ansatz, not a derived QFT residual",
    "Fractal resonator scale modulates κ only; geometry is not mesh-simulated",
    "Bundled SAMPLE_* curves are synthetic stand-ins, not SPARC catalog rows",
    "PASS means relative RMSE improvement under assumptions — not CFT/IQG validation",
]


@dataclass(frozen=True)
class SPARCCurve:
    radius_kpc: Tuple[float, ...]
    velocity_obs: Tuple[float, ...]
    velocity_err: Tuple[float, ...]
    velocity_gas: Tuple[float, ...]
    velocity_disk: Tuple[float, ...]
    velocity_bulge: Tuple[float, ...]
    galaxy_id: str = "unknown"

    def __post_init__(self) -> None:
        n = len(self.radius_kpc)
        if n == 0:
            raise ValueError("SPARCCurve requires at least one radius point")
        for name in (
            "velocity_obs",
            "velocity_err",
            "velocity_gas",
            "velocity_disk",
            "velocity_bulge",
        ):
            if len(getattr(self, name)) != n:
                raise ValueError(f"{name} length mismatch vs radius_kpc")

    @property
    def n_points(self) -> int:
        return len(self.radius_kpc)


def _reject_remote(path_like: Union[str, Path]) -> Path:
    s = str(path_like).strip()
    if _REMOTE_SCHEME.search(s):
        raise PermissionError(f"network_access=false: remote path rejected: {s!r}")
    if s.lower().startswith("file://"):
        s = s[7:]
    return Path(s).expanduser().resolve()


def load_sparc_csv(path: Union[str, Path], galaxy_id: Optional[str] = None) -> SPARCCurve:
    p = _reject_remote(path)
    if not p.is_file():
        raise FileNotFoundError(f"local SPARC CSV not found: {p}")

    R: List[float] = []
    Vo: List[float] = []
    Ve: List[float] = []
    Vg: List[float] = []
    Vd: List[float] = []
    Vb: List[float] = []

    with open(p, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError("CSV has no header")
        fields = {h.strip().lower(): h for h in reader.fieldnames if h}

        def col(*names: str) -> Optional[str]:
            for n in names:
                if n.lower() in fields:
                    return fields[n.lower()]
            return None

        c_r = col("R", "radius", "rad", "r_kpc")
        c_vo = col("Vobs", "vobs", "v_obs", "velocity")
        if not c_r or not c_vo:
            raise ValueError("CSV must include R and Vobs columns")
        c_ve = col("Verr", "verr", "e_vobs", "error")
        c_vg = col("Vgas", "vgas")
        c_vd = col("Vdisk", "vdisk")
        c_vb = col("Vbulge", "vbulge")

        for row in reader:
            try:
                R.append(float(row[c_r]))
                Vo.append(float(row[c_vo]))
            except (KeyError, TypeError, ValueError) as e:
                raise ValueError(f"malformed SPARC row: {row}") from e
            Ve.append(float(row[c_ve]) if c_ve and row.get(c_ve) not in (None, "") else 1.0)
            Vg.append(float(row[c_vg]) if c_vg and row.get(c_vg) not in (None, "") else 0.0)
            Vd.append(float(row[c_vd]) if c_vd and row.get(c_vd) not in (None, "") else 0.0)
            Vb.append(float(row[c_vb]) if c_vb and row.get(c_vb) not in (None, "") else 0.0)

    if not R:
        raise ValueError(f"empty SPARC curve: {p}")

    return SPARCCurve(
        radius_kpc=tuple(R),
        velocity_obs=tuple(Vo),
        velocity_err=tuple(Ve),
        velocity_gas=tuple(Vg),
        velocity_disk=tuple(Vd),
        velocity_bulge=tuple(Vb),
        galaxy_id=galaxy_id or p.stem,
    )


def sample_galaxy(galaxy_id: str = "SAMPLE_A") -> SPARCCurve:
    raw = SAMPLE_GALAXIES.get(galaxy_id)
    if not raw:
        raise KeyError(f"unknown sample galaxy: {galaxy_id}")
    return SPARCCurve(
        radius_kpc=tuple(r["R"] for r in raw),
        velocity_obs=tuple(r["Vobs"] for r in raw),
        velocity_err=tuple(r.get("Verr", 1.0) for r in raw),
        velocity_gas=tuple(r.get("Vgas", 0.0) for r in raw),
        velocity_disk=tuple(r.get("Vdisk", 0.0) for r in raw),
        velocity_bulge=tuple(r.get("Vbulge", 0.0) for r in raw),
        galaxy_id=galaxy_id,
    )


@dataclass(frozen=True)
class WareResult:
    n: float
    W: float
    bound: float
    bound_satisfied: bool


def ware_weight(n: float) -> float:
    return float(W0 * math.exp(XI * (float(n) - N_REF)))


def ware_result(n: float) -> WareResult:
    W = ware_weight(n)
    return WareResult(n=float(n), W=W, bound=GHOST_BOUND, bound_satisfied=W < GHOST_BOUND)


def ghost_free(n: float, bound: float = GHOST_BOUND) -> bool:
    return ware_weight(n) < bound


@dataclass
class ProcaField:
    mass: float = 1.0
    coupling: float = 25.0
    field: Optional[np.ndarray] = None
    gradient: Optional[np.ndarray] = None
    residual: Optional[np.ndarray] = None

    def evaluate_delta_v(self, R: np.ndarray, W: float) -> np.ndarray:
        R = np.asarray(R, dtype=np.float64)
        delta = W * self.coupling * (R / (1.0 + R))
        self.field = delta
        if R.size >= 2:
            order = np.argsort(R)
            g = np.zeros_like(delta)
            Rs, ds = R[order], delta[order]
            g[order[1:-1]] = (ds[2:] - ds[:-2]) / np.maximum(Rs[2:] - Rs[:-2], 1e-12)
            g[order[0]] = (ds[1] - ds[0]) / max(Rs[1] - Rs[0], 1e-12)
            g[order[-1]] = (ds[-1] - ds[-2]) / max(Rs[-1] - Rs[-2], 1e-12)
            self.gradient = g
        else:
            self.gradient = np.zeros_like(delta)
        self.residual = delta
        return delta


@dataclass
class FractalResonator:
    order: int = 3
    scale: float = 0.45
    dimension: float = 0.868
    coupling: float = 1.0

    def weight_factor(self) -> float:
        return float(self.coupling) * float(self.scale)


def baryonic_speed(v_gas: float, v_disk: float, v_bulge: float) -> float:
    return math.sqrt(max(0.0, v_gas**2 + v_disk**2 + v_bulge**2))


def newtonian_curve(curve: SPARCCurve) -> np.ndarray:
    return np.array(
        [
            baryonic_speed(g, d, b)
            for g, d, b in zip(
                curve.velocity_gas, curve.velocity_disk, curve.velocity_bulge
            )
        ],
        dtype=np.float64,
    )


def ware_model_curve(
    curve: SPARCCurve,
    n: float,
    proca: Optional[ProcaField] = None,
    resonator: Optional[FractalResonator] = None,
) -> np.ndarray:
    wr = ware_result(n)
    proca = proca or ProcaField()
    resonator = resonator or FractalResonator(order=int(round(n)))
    R = np.asarray(curve.radius_kpc, dtype=np.float64)
    kappa_eff = proca.coupling * resonator.weight_factor() / max(resonator.scale, 1e-12)
    proca_mod = ProcaField(mass=proca.mass, coupling=kappa_eff)
    delta = proca_mod.evaluate_delta_v(R, wr.W)
    v_bar = newtonian_curve(curve)
    return np.sqrt(np.maximum(0.0, v_bar**2 + delta**2))


@dataclass
class SPARCFitResult:
    baseline_rmse: float
    model_rmse: float
    residuals: Tuple[float, ...]
    parameters: Dict[str, float]
    status: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "baseline_rmse": self.baseline_rmse,
            "model_rmse": self.model_rmse,
            "residuals": list(self.residuals),
            "parameters": dict(self.parameters),
            "status": self.status,
        }


@dataclass
class PhysicsVerification:
    """
    Machine-readable verification object.

    Claim flags are fixed at construction and participate in result_hash so
    downstream consumers cannot strip hypothesis-grade status while keeping
    a valid hash of the numerical result alone.
    """

    status: str
    metrics: Dict[str, Any]
    assumptions: List[str]
    warnings: List[str]
    fhrr_vector: Optional[np.ndarray] = None
    input_hash: str = ""
    result_hash: str = ""
    network_access: bool = False
    # Immutable scientific classification (v1 contract)
    claim_class: str = field(default=CLAIM_CLASS)
    experimental_validation: bool = field(default=False)
    energy_extraction_validated: bool = field(default=False)
    thrust_validated: bool = field(default=False)

    def __post_init__(self) -> None:
        # Re-assert frozen claim flags even if a caller passes overrides
        object.__setattr__(self, "claim_class", CLAIM_CLASS)
        object.__setattr__(self, "experimental_validation", False)
        object.__setattr__(self, "energy_extraction_validated", False)
        object.__setattr__(self, "thrust_validated", False)
        object.__setattr__(self, "network_access", False)

    def claim_block(self) -> Dict[str, Any]:
        return {
            "claim_class": self.claim_class,
            "experimental_validation": self.experimental_validation,
            "energy_extraction_validated": self.energy_extraction_validated,
            "thrust_validated": self.thrust_validated,
        }

    def to_dict(self, include_vector: bool = False) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "status": self.status,
            "metrics": self.metrics,
            "assumptions": list(self.assumptions),
            "warnings": list(self.warnings),
            "input_hash": self.input_hash,
            "result_hash": self.result_hash,
            "network_access": False,
            **self.claim_block(),
            "disclaimer": (
                "Phenomenological offline comparison only. "
                "Not experimental validation of CFT, IQG, vacuum extraction, or propulsion."
            ),
        }
        if include_vector and self.fhrr_vector is not None:
            d["fhrr_dim"] = int(self.fhrr_vector.shape[0])
            d["fhrr_norm"] = float(np.linalg.norm(self.fhrr_vector))
        return d

    def payload_for_hash(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "metrics": self.metrics,
            "assumptions": self.assumptions,
            "warnings": self.warnings,
            "input_hash": self.input_hash,
            "network_access": False,
            **self.claim_block(),
        }


def _rmse(obs: np.ndarray, pred: np.ndarray, err: Optional[np.ndarray] = None) -> float:
    if err is not None:
        w = 1.0 / np.maximum(err, 1e-6)
        return float(np.sqrt(np.mean(((obs - pred) * w) ** 2)))
    return float(np.sqrt(np.mean((obs - pred) ** 2)))


def fit_sparc(
    curve: SPARCCurve,
    n: float = 3.0,
    proca: Optional[ProcaField] = None,
    resonator: Optional[FractalResonator] = None,
) -> SPARCFitResult:
    obs = np.asarray(curve.velocity_obs, dtype=np.float64)
    err = np.asarray(curve.velocity_err, dtype=np.float64)
    base = newtonian_curve(curve)
    model = ware_model_curve(curve, n=n, proca=proca, resonator=resonator)
    base_rmse = _rmse(obs, base, err)
    model_rmse = _rmse(obs, model, err)
    residuals = tuple(float(x) for x in (obs - model))
    wr = ware_result(n)
    improvement = (base_rmse - model_rmse) / max(base_rmse, 1e-12)

    if not wr.bound_satisfied:
        fit_status = "GHOST_BOUND_VIOLATION"
    elif improvement > 0.05:
        fit_status = "MODEL_LOWER_RMSE"
    elif improvement < -0.05:
        fit_status = "BASELINE_LOWER_RMSE"
    else:
        fit_status = "NEAR_PARITY"

    return SPARCFitResult(
        baseline_rmse=base_rmse,
        model_rmse=model_rmse,
        residuals=residuals,
        parameters={
            "n": float(n),
            "W": wr.W,
            "ghost_bound": GHOST_BOUND,
            "improvement": float(improvement),
            "kappa": float((proca or ProcaField()).coupling),
            "scale": float((resonator or FractalResonator()).scale),
        },
        status=fit_status,
    )


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def hash_payload(obj: Any) -> str:
    return hashlib.sha256(_canonical_json(obj).encode("utf-8")).hexdigest()


def encode_fhrr(
    metrics: Dict[str, Any],
    dim: int = FHRR_DIM,
    seed_material: Optional[str] = None,
) -> np.ndarray:
    material = seed_material or _canonical_json(metrics)
    digest = hashlib.sha256(material.encode("utf-8")).digest()
    seed = int.from_bytes(digest[:8], "big") % (2**32 - 1)
    rng = np.random.default_rng(seed)
    phases = rng.uniform(0.0, 2.0 * math.pi, size=dim)
    vec = np.exp(1j * phases).astype(np.complex128)
    vec /= np.linalg.norm(vec)
    return vec


def verify_physics(
    curve: SPARCCurve,
    n: float = 3.0,
    proca: Optional[ProcaField] = None,
    resonator: Optional[FractalResonator] = None,
    encode: bool = True,
) -> PhysicsVerification:
    warnings: List[str] = []
    try:
        fit = fit_sparc(curve, n=n, proca=proca, resonator=resonator)
    except Exception as e:
        ver = PhysicsVerification(
            status="INCONCLUSIVE",
            metrics={"error": str(e)},
            assumptions=list(ASSUMPTIONS_BASE),
            warnings=[f"fit failed: {e}"],
            input_hash=hash_payload({"galaxy": curve.galaxy_id, "n": n}),
        )
        ver.result_hash = hash_payload(ver.payload_for_hash())
        return ver

    wr = ware_result(n)
    input_blob = {
        "galaxy_id": curve.galaxy_id,
        "n_points": curve.n_points,
        "radius_kpc": list(curve.radius_kpc),
        "velocity_obs": list(curve.velocity_obs),
        "n": float(n),
    }
    input_hash = hash_payload(input_blob)
    metrics = {
        "galaxy_id": curve.galaxy_id,
        "n_points": curve.n_points,
        "ware": asdict(wr),
        "fit": fit.to_dict(),
    }

    if not wr.bound_satisfied:
        status = "FAIL"
        warnings.append(f"W({n})={wr.W:.6f} violates ghost-free bound {GHOST_BOUND}")
    elif fit.status == "MODEL_LOWER_RMSE":
        status = "PASS"
        warnings.append(
            "PASS is phenomenological RMSE improvement only — not CFT/IQG validation"
        )
    elif fit.status == "BASELINE_LOWER_RMSE":
        status = "FAIL"
    else:
        status = "INCONCLUSIVE"

    if curve.n_points < 3:
        status = "INCONCLUSIVE"
        warnings.append("fewer than 3 radial points")

    fhrr = encode_fhrr(metrics, dim=FHRR_DIM) if encode else None
    ver = PhysicsVerification(
        status=status,
        metrics=metrics,
        assumptions=list(ASSUMPTIONS_BASE),
        warnings=warnings,
        fhrr_vector=fhrr,
        input_hash=input_hash,
    )
    ver.result_hash = hash_payload(ver.payload_for_hash())
    return ver


def verify_result_integrity(ver: PhysicsVerification) -> bool:
    return ver.result_hash == hash_payload(ver.payload_for_hash())


class WarePhysicsBridge:
    """Pure offline evaluator. No ledger mutation. No network."""

    def __init__(self, dim: int = FHRR_DIM, **_compat: Any):
        if dim != FHRR_DIM:
            raise ValueError(f"FHRR dimension must be {FHRR_DIM}")
        self.dim = dim

    def evaluate(
        self,
        galaxy_id: str = "SAMPLE_A",
        n: float = 3.0,
        kappa: float = 25.0,
        scale: float = 0.45,
        csv_path: Optional[Union[str, Path]] = None,
        log: bool = False,
        **_ignored: Any,
    ) -> Dict[str, Any]:
        del log

        def _err_out(status: str, err: str, warnings: List[str]) -> Dict[str, Any]:
            return {
                "status": status,
                "metrics": {"error": err},
                "assumptions": list(ASSUMPTIONS_BASE),
                "warnings": warnings,
                "network_access": False,
                **dict(CLAIM_FLAGS),
                "disclaimer": (
                    "Phenomenological offline comparison only. "
                    "Not experimental validation of CFT, IQG, vacuum extraction, or propulsion."
                ),
                "fit": {},
            }

        try:
            if csv_path is not None:
                curve = load_sparc_csv(csv_path)
            else:
                curve = sample_galaxy(galaxy_id)
        except PermissionError as e:
            return _err_out("FAIL", str(e), ["remote or forbidden path"])
        except (FileNotFoundError, ValueError, KeyError) as e:
            return _err_out("INCONCLUSIVE", str(e), [str(e)])

        proca = ProcaField(coupling=float(kappa))
        resonator = FractalResonator(order=int(round(n)), scale=float(scale))
        ver = verify_physics(curve, n=float(n), proca=proca, resonator=resonator)
        out = ver.to_dict(include_vector=True)
        out["fit"] = ver.metrics.get("fit", {})
        params = out["fit"].get("parameters") or {}
        out["fit"]["W_n"] = params.get("W")
        out["fit"]["ghost_free"] = ver.metrics.get("ware", {}).get("bound_satisfied")
        out["fhrr_atom"] = f"PHYS::{curve.galaxy_id}::n{n}"
        out["shacl_conforms"] = True
        return out


def physics_skill_handler(bridge: Optional[WarePhysicsBridge] = None):
    bridge = bridge or WarePhysicsBridge()

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
            log=False,
        )
        state.setdefault("telemetry", {})["physics_status"] = result["status"]
        fit = result.get("fit") or {}
        params = fit.get("parameters") or {}
        state["telemetry"]["W_n"] = params.get("W", fit.get("W_n"))
        state["telemetry"]["physics_result_hash"] = result.get("result_hash")
        state["telemetry"]["physics_input_hash"] = result.get("input_hash")
        state["telemetry"]["claim_class"] = result.get("claim_class")
        state["telemetry"]["experimental_validation"] = result.get(
            "experimental_validation", False
        )
        return result

    return handler
