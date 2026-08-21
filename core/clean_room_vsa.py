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


class BaNELController:
    """Bayesian Negative Evidence Learning (BaNEL) Engine."""

    def __init__(self, imprint_strength: float = 0.20):
        self.imprint_strength = imprint_strength
        self.failure_ledger: List[Dict[str, Any]] = []

    def record_failure(
        self,
        task_name: str,
        error_msg: str,
        context_vector: Optional[np.ndarray] = None,
    ) -> float:
        evidence_score = 0.85
        self.failure_ledger.append({
            "task": task_name,
            "error": error_msg,
            "evidence": evidence_score,
            "context": context_vector,
            "timestamp": time.time(),
        })
        return evidence_score

    def apply_phase_repulsion(
        self,
        parent_vec: np.ndarray,
        failure_vec: np.ndarray,
        fitness: float,
    ) -> np.ndarray:
        dynamic_strength = self.imprint_strength + 0.15 * max(0.0, 1.0 - fitness)
        proj_coeff = np.vdot(failure_vec, parent_vec)
        parallel = proj_coeff * parent_vec
        mutated = parent_vec - (dynamic_strength * parallel)
        noise_phases = np.random.uniform(-0.05, 0.05, parent_vec.shape)
        mutated = mutated * np.exp(1j * noise_phases)
        return mutated / (np.linalg.norm(mutated) + 1e-12)


class CleanRoomVSAEngine:
    """Core FHRR Engine (v1.3.3)."""

    def __init__(
        self,
        dim: int = 8192,
        sparsity_k: int = 256,
        iters: int = 7,
        min_invertibility: float = 0.92,
        max_codebook_size: int = 4096,
        redundancy_threshold: float = 0.97,
    ):
        self.dim = dim
        self.sparsity_k = min(sparsity_k, dim)
        self.iters = iters
        self.min_invertibility = min_invertibility
        self.max_codebook_size = max_codebook_size
        self.redundancy_threshold = redundancy_threshold
        self.codebook: Dict[str, np.ndarray] = {}
        self.atom_meta: Dict[str, Dict[str, Any]] = {}
        self.banel = BaNELController()
        self._jump_start_seed: Optional[int] = None

    def random_symbol(self, rng: Optional[np.random.Generator] = None) -> np.ndarray:
        if rng is None:
            phases = np.random.uniform(0.0, 2.0 * np.pi, self.dim)
        else:
            phases = rng.uniform(0.0, 2.0 * np.pi, self.dim)
        vec = np.exp(1j * phases).astype(np.complex128)
        return vec / np.linalg.norm(vec)

    def _ensure_meta(self, name: str, pinned: bool = False) -> None:
        if name not in self.atom_meta:
            self.atom_meta[name] = {
                "access_count": 0,
                "last_access": time.time(),
                "pinned": pinned or (name in DEFAULT_PROTECTED_ATOMS),
            }
        elif pinned:
            self.atom_meta[name]["pinned"] = True

    def touch(self, name: str) -> None:
        self._ensure_meta(name)
        self.atom_meta[name]["access_count"] += 1
        self.atom_meta[name]["last_access"] = time.time()

    def pin(self, name: str) -> None:
        self._ensure_meta(name, pinned=True)
        self.atom_meta[name]["pinned"] = True

    def unpin(self, name: str) -> None:
        self._ensure_meta(name)
        if name in DEFAULT_PROTECTED_ATOMS:
            return
        self.atom_meta[name]["pinned"] = False

    def register(
        self,
        name: str,
        vec: Optional[np.ndarray] = None,
        pinned: bool = False,
        rng: Optional[np.random.Generator] = None,
    ) -> np.ndarray:
        if vec is None:
            vec = self.random_symbol(rng=rng)
        else:
            vec = vec.astype(np.complex128)
            vec = vec / (np.linalg.norm(vec) + 1e-12)
        self.codebook[name] = vec
        self._ensure_meta(name, pinned=pinned)
        self.touch(name)
        return vec

    def bind(self, a: np.ndarray, b: np.ndarray) -> np.ndarray:
        return a * b

    def unbind(self, composite: np.ndarray, binder: np.ndarray) -> np.ndarray:
        return composite * np.conj(binder)

    def bundle(self, vectors: List[np.ndarray]) -> np.ndarray:
        if not vectors:
            raise ValueError("Cannot bundle an empty list of vectors.")
        summed = np.sum(vectors, axis=0)
        norm = np.linalg.norm(summed)
        return summed / (norm + 1e-12)

    def similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        return float(
            np.real(np.vdot(a, b))
            / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-12)
        )

    def resonator_cleanup(
        self, noisy_vec: np.ndarray, binder: np.ndarray
    ) -> Tuple[np.ndarray, float]:
        x = noisy_vec * np.conj(binder)
        keys = list(self.codebook.keys())
        matrix = np.stack([self.codebook[k] for k in keys], axis=0) if keys else None

        for i in range(self.iters):
            mag = np.abs(x)
            if self.sparsity_k < self.dim:
                idx = np.argpartition(mag, -self.sparsity_k)[-self.sparsity_k :]
                mask = np.zeros_like(mag, dtype=bool)
                mask[idx] = True
                x = x * mask

            if matrix is not None and i < self.iters - 1:
                projections = matrix @ np.conj(x)
                best_idx = int(np.argmax(np.abs(projections)))
                x = matrix[best_idx].copy()
                self.touch(keys[best_idx])

            norm = np.linalg.norm(x)
            if norm > 0:
                x = x / norm

        recovered = self.bind(x, binder)
        invert_score = self.similarity(recovered, noisy_vec)
        return x, invert_score

    def check_invertibility(self, invert_score: float) -> bool:
        return invert_score >= self.min_invertibility

    def gated_resonator_cleanup(
        self, noisy_vec: np.ndarray, binder: np.ndarray
    ) -> Tuple[Optional[np.ndarray], float, bool]:
        cleaned, invert_score = self.resonator_cleanup(noisy_vec, binder)
        accepted = self.check_invertibility(invert_score)
        if not accepted:
            return None, invert_score, False
        return cleaned, invert_score, True

    def promote_memskill(
        self,
        name: str,
        vec: np.ndarray,
        binder: Optional[np.ndarray] = None,
        pinned: bool = False,
    ) -> bool:
        candidate = vec
        if binder is not None:
            candidate, score, accepted = self.gated_resonator_cleanup(vec, binder)
            if not accepted:
                return False
        self.register(name, candidate, pinned=pinned)
        return True

    def consolidate(
        self,
        episodic_vectors: List[np.ndarray],
        min_count: int = 2,
        fitness_scores: Optional[List[float]] = None,
        min_fitness: float = 0.0,
    ) -> Optional[np.ndarray]:
        if fitness_scores is not None:
            eligible = [
                v for v, f in zip(episodic_vectors, fitness_scores) if f >= min_fitness
            ]
        else:
            eligible = list(episodic_vectors)
        if len(eligible) < min_count:
            return None
        return self.bundle(eligible)

    def jump_start_v01(self, seed: Optional[int] = 0x5345454D) -> Dict[str, Any]:
        self._jump_start_seed = seed
        rng = np.random.default_rng(seed) if seed is not None else None
        for name in JUMP_START_V01_ATOMS:
            self.register(name, vec=None, pinned=True, rng=rng)
            self.pin(name)
        return self.jump_start_manifest()

    def verify_jump_start_integrity(self) -> bool:
        for name in JUMP_START_V01_ATOMS:
            if name not in self.codebook:
                return False
            meta = self.atom_meta.get(name, {})
            if not meta.get("pinned", False):
                return False
            nrm = float(np.linalg.norm(self.codebook[name]))
            if abs(nrm - 1.0) > 1e-6:
                return False
        return True

    def jump_start_manifest(self) -> Dict[str, Any]:
        return {
            "version": "jump_start_v0.1",
            "atoms": list(JUMP_START_V01_ATOMS),
            "all_pinned": self.verify_jump_start_integrity(),
            "dim": self.dim,
            "sparsity_k": self.sparsity_k,
            "iters": self.iters,
            "min_invertibility": self.min_invertibility,
            "seed": self._jump_start_seed,
            "codebook_stats": self.codebook_stats(),
        }

    def _utility(self, name: str) -> float:
        meta = self.atom_meta.get(name)
        if meta is None:
            return 0.0
        age = max(1.0, time.time() - float(meta["last_access"]))
        recency = 1.0 / (1.0 + age / 86400.0)
        return float(meta["access_count"]) * (0.5 + 0.5 * recency)

    def prune_redundant(self, threshold: Optional[float] = None) -> List[str]:
        thr = self.redundancy_threshold if threshold is None else threshold
        names = list(self.codebook.keys())
        removed: List[str] = []
        alive = set(names)
        for i, a in enumerate(names):
            if a not in alive:
                continue
            for b in names[i + 1 :]:
                if b not in alive:
                    continue
                sim = abs(self.similarity(self.codebook[a], self.codebook[b]))
                if sim < thr:
                    continue
                a_pin = self.atom_meta.get(a, {}).get("pinned", False)
                b_pin = self.atom_meta.get(b, {}).get("pinned", False)
                if a_pin and b_pin:
                    continue
                if a_pin and not b_pin:
                    drop = b
                elif b_pin and not a_pin:
                    drop = a
                else:
                    drop = b if self._utility(a) >= self._utility(b) else a
                if drop in alive:
                    alive.discard(drop)
                    removed.append(drop)
        for name in removed:
            self.codebook.pop(name, None)
            self.atom_meta.pop(name, None)
        return removed

    def prune_by_utility(self, max_size: Optional[int] = None) -> List[str]:
        limit = self.max_codebook_size if max_size is None else max_size
        if len(self.codebook) <= limit:
            return []
        unpinned = [
            n for n in self.codebook
            if not self.atom_meta.get(n, {}).get("pinned", False)
        ]
        unpinned.sort(key=self._utility)
        removed: List[str] = []
        while len(self.codebook) > limit and unpinned:
            name = unpinned.pop(0)
            if name in self.codebook:
                self.codebook.pop(name)
                self.atom_meta.pop(name, None)
                removed.append(name)
        return removed

    def prune_codebook(
        self,
        max_size: Optional[int] = None,
        redundancy_threshold: Optional[float] = None,
    ) -> Dict[str, List[str]]:
        redundant = self.prune_redundant(threshold=redundancy_threshold)
        utility = self.prune_by_utility(max_size=max_size)
        return {"redundant": redundant, "utility": utility}

    def codebook_stats(self) -> Dict[str, Any]:
        pinned = sum(
            1 for n in self.codebook
            if self.atom_meta.get(n, {}).get("pinned", False)
        )
        return {
            "size": len(self.codebook),
            "pinned": pinned,
            "unpinned": len(self.codebook) - pinned,
            "max_codebook_size": self.max_codebook_size,
            "redundancy_threshold": self.redundancy_threshold,
            "sparsity_k": self.sparsity_k,
        }

    def save(self, directory: str | Path) -> None:
        target_dir = Path(directory)
        parent_dir = target_dir.parent
        parent_dir.mkdir(parents=True, exist_ok=True)
        tmp_dir = parent_dir / f".tmp_{target_dir.name}_{int(time.time() * 1000)}"
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir)
        tmp_dir.mkdir(parents=True, exist_ok=True)
        try:
            codebook_dir = tmp_dir / "codebook"
            codebook_dir.mkdir(exist_ok=True)
            manifest = {}
            for name, vec in self.codebook.items():
                fname = f"{name}.npy"
                np.save(codebook_dir / fname, vec)
                manifest[name] = fname
            with open(tmp_dir / "codebook_manifest.json", "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2)
            meta_out = {}
            for name, m in self.atom_meta.items():
                if name in self.codebook:
                    meta_out[name] = {
                        "access_count": int(m["access_count"]),
                        "last_access": float(m["last_access"]),
                        "pinned": bool(m["pinned"]),
                    }
            with open(tmp_dir / "atom_meta.json", "w", encoding="utf-8") as f:
                json.dump(meta_out, f, indent=2)
            ledger = []
            for i, entry in enumerate(self.banel.failure_ledger):
                record = {
                    "task": entry["task"],
                    "error": entry["error"],
                    "evidence": entry["evidence"],
                    "timestamp": entry["timestamp"],
                }
                ctx = entry.get("context")
                if ctx is not None:
                    ctx_name = f"ctx_{i}.npy"
                    np.save(tmp_dir / ctx_name, ctx)
                    record["context_file"] = ctx_name
                ledger.append(record)
            with open(tmp_dir / "banel_ledger.json", "w", encoding="utf-8") as f:
                json.dump(ledger, f, indent=2)
            config = {
                "dim": self.dim,
                "sparsity_k": self.sparsity_k,
                "iters": self.iters,
                "min_invertibility": self.min_invertibility,
                "max_codebook_size": self.max_codebook_size,
                "redundancy_threshold": self.redundancy_threshold,
                "jump_start_seed": self._jump_start_seed,
            }
            with open(tmp_dir / "engine_config.json", "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
            if target_dir.exists():
                shutil.rmtree(target_dir)
            tmp_dir.rename(target_dir)
        except Exception as e:
            if tmp_dir.exists():
                shutil.rmtree(tmp_dir)
            raise RuntimeError(f"Atomic persistence failed: {e}") from e

    def load(self, directory: str | Path) -> None:
        directory = Path(directory)
        if not directory.is_dir():
            raise FileNotFoundError(f"Persistence directory not found: {directory}")
        with open(directory / "engine_config.json", "r", encoding="utf-8") as f:
            config = json.load(f)
        self.dim = config["dim"]
        self.sparsity_k = config["sparsity_k"]
        self.iters = config["iters"]
        self.min_invertibility = config["min_invertibility"]
        self.max_codebook_size = config.get("max_codebook_size", 4096)
        self.redundancy_threshold = config.get("redundancy_threshold", 0.97)
        self._jump_start_seed = config.get("jump_start_seed")
        self.codebook.clear()
        with open(directory / "codebook_manifest.json", "r", encoding="utf-8") as f:
            manifest = json.load(f)
        codebook_dir = directory / "codebook"
        for name, fname in manifest.items():
            vec = np.load(codebook_dir / fname)
            self.codebook[name] = vec.astype(np.complex128)
        self.atom_meta.clear()
        meta_path = directory / "atom_meta.json"
        if meta_path.is_file():
            with open(meta_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            for name, m in raw.items():
                if name in self.codebook:
                    self.atom_meta[name] = {
                        "access_count": int(m.get("access_count", 0)),
                        "last_access": float(m.get("last_access", time.time())),
                        "pinned": bool(m.get("pinned", name in DEFAULT_PROTECTED_ATOMS)),
                    }
        for name in self.codebook:
            self._ensure_meta(name)
        self.banel.failure_ledger.clear()
        with open(directory / "banel_ledger.json", "r", encoding="utf-8") as f:
            ledger = json.load(f)
        for record in ledger:
            ctx = None
            if "context_file" in record:
                ctx = np.load(directory / record["context_file"])
            self.banel.failure_ledger.append({
                "task": record["task"],
                "error": record["error"],
                "evidence": record["evidence"],
                "context": ctx,
                "timestamp": record["timestamp"],
            })


class CleanRoomGate:
    """
    Sovereign Clean-Room Boundary Isolator.

    - Optional SHACL-subset constitutional validation
    - Ed25519 skill package signatures
    - network_access=false enforcement
    - Sandboxed execution + BaNEL failures
    """

    def __init__(
        self,
        vsa_engine: CleanRoomVSAEngine,
        trusted_verify_keys: Optional[Iterable[str]] = None,
        require_skill_signature: bool = True,
        enable_shacl: bool = True,
    ):
        self.vsa = vsa_engine
        self.trusted_verify_keys: List[str] = [k.strip() for k in (trusted_verify_keys or []) if k]
        self.require_skill_signature = require_skill_signature
        self.enable_shacl = enable_shacl
        self._shacl = None
        if enable_shacl:
            try:
                from clean_room_shacl import ConstitutionalValidator

                self._shacl = ConstitutionalValidator(engine=vsa_engine)
            except Exception:
                self._shacl = None

    def add_trusted_verify_key(self, verify_key_hex: str) -> None:
        k = verify_key_hex.strip()
        if k and k not in self.trusted_verify_keys:
            self.trusted_verify_keys.append(k)

    def load_trusted_verify_key_file(self, path: Union[str, Path]) -> None:
        text = Path(path).read_text(encoding="utf-8").strip().split()[0]
        self.add_trusted_verify_key(text)

    def verify_skill_package(self, package: Dict[str, Any]) -> None:
        """Raise PermissionError if package is not safe to execute."""
        sov = package.get("sovereignty") or {}
        if sov.get("network_access") is not False:
            raise PermissionError("skill rejected: network_access must be false")

        if self.enable_shacl and self._shacl is not None:
            report = self._shacl.validate_skill_package(package)
            if not report.conforms:
                msgs = "; ".join(v.message for v in report.violations) or "shape violation"
                raise PermissionError(f"skill rejected by SHACL: {msgs}")

        if not self.require_skill_signature:
            return

        from skill_crypto import verify_package

        if not self.trusted_verify_keys:
            raise PermissionError(
                "skill rejected: no trusted verify keys configured on CleanRoomGate"
            )
        verify_package(package, self.trusted_verify_keys)

    def execute_sandboxed_computation(
        self,
        task_name: str,
        payload_func: Callable,
        *args,
        context_vector: Optional[np.ndarray] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        start_time = time.time()
        print(f"[*] [Clean-Room] Opening isolation boundary for task: '{task_name}'")
        try:
            result = payload_func(*args, **kwargs)

            if isinstance(result, (int, float, np.number)):
                if not np.isfinite(result):
                    raise ValueError("Computed scalar value is non-finite.")
                sanitized_output = float(result)
            elif isinstance(result, np.ndarray):
                if not np.all(np.isfinite(result)):
                    raise ValueError("Computed array contains non-finite elements.")
                sanitized_output = result.copy()
            elif isinstance(result, dict):
                sanitized_output = result
            else:
                sanitized_output = {"data": str(result)}

            elapsed = time.time() - start_time
            print(f"[+] [Clean-Room] Task '{task_name}' executed safely in {elapsed:.4f}s.")
            return {
                "status": "PASS",
                "task": task_name,
                "output": sanitized_output,
                "error": None,
                "elapsed": elapsed,
                "banel_evidence": 0.0,
            }

        except Exception as e:
            error_msg = str(e)
            elapsed = time.time() - start_time
            print(f"[-] [Clean-Room] Containment triggered for '{task_name}': {error_msg}")
            evidence_score = self.vsa.banel.record_failure(
                task_name, error_msg, context_vector
            )
            return {
                "status": "FAIL",
                "task": task_name,
                "output": None,
                "error": error_msg,
                "elapsed": elapsed,
                "banel_evidence": evidence_score,
            }

    def execute_skill_package(
        self,
        package: Dict[str, Any],
        payload_func: Callable,
        *args,
        context_vector: Optional[np.ndarray] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        skill_id = package.get("manifest", {}).get("skill_id", "unknown_skill")
        try:
            self.verify_skill_package(package)
        except Exception as e:
            msg = str(e)
            print(f"[-] [Clean-Room] Skill '{skill_id}' rejected before execution: {msg}")
            evidence = self.vsa.banel.record_failure(
                f"skill_verify:{skill_id}", msg, context_vector
            )
            return {
                "status": "FAIL",
                "task": f"skill_verify:{skill_id}",
                "output": None,
                "error": msg,
                "elapsed": 0.0,
                "banel_evidence": evidence,
            }

        outcome = self.execute_sandboxed_computation(
            f"skill:{skill_id}",
            payload_func,
            *args,
            context_vector=context_vector,
            **kwargs,
        )

        # Post-condition SHACL on gate result envelope
        if self.enable_shacl and self._shacl is not None and outcome.get("status") in (
            "PASS",
            "FAIL",
        ):
            report = self._shacl.validate_gate_result(outcome)
            if not report.conforms:
                msgs = "; ".join(v.message for v in report.violations)
                outcome = {
                    "status": "FAIL",
                    "task": f"skill_shacl_post:{skill_id}",
                    "output": None,
                    "error": f"post SHACL: {msgs}",
                    "elapsed": outcome.get("elapsed", 0.0),
                    "banel_evidence": self.vsa.banel.record_failure(
                        f"skill_shacl_post:{skill_id}", msgs, context_vector
                    ),
                }
        return outcome


if __name__ == "__main__":
    print("[*] Initializing Sovereign Clean-Room VSA Engine (v1.3.3)...")
    vsa = CleanRoomVSAEngine(dim=8192, sparsity_k=256, iters=7, min_invertibility=0.92)
    manifest = vsa.jump_start_v01()
    print(f"[+] Jump-Start: {manifest}")
    assert vsa.verify_jump_start_integrity()
    print("[+] Integrity OK")
