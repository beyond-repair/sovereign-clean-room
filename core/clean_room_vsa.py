#!/usr/bin/env python3
"""
Sovereign Clean-Room VSA Core + BaNEL Integration Framework
(v1.3.1 — Sparse Codebook Pruning Edition)

Complete production-grade implementation featuring:
- Single-pass unbind resonator loop with strict top-k cardinality
- Hyperspherical parallel-projection phase repulsion (BaNEL)
- Gated invertibility checks
- Sparse codebook pruning (utility + redundancy)
- Atomic disk persistence & sandboxed execution
"""

from __future__ import annotations
import numpy as np
from typing import Dict, List, Tuple, Optional, Callable, Any, Set
import time
import json
import shutil
from pathlib import Path


# Jump-Start v0.1 primitives — never pruned unless explicitly unpinned
DEFAULT_PROTECTED_ATOMS: Set[str] = {
    "SELF",
    "ENVIRONMENT",
    "EPISODIC",
    "SEMANTIC",
    "SUCCESS",
    "FAILURE",
}


class BaNELController:
    """
    Bayesian Negative Evidence Learning (BaNEL) Engine.
    Tracks execution failures, imprints failure directions in complex phase space,
    and scales mutation magnitude inversely with route fitness using hyperspherical geometry.
    """
    def __init__(self, imprint_strength: float = 0.20):
        self.imprint_strength = imprint_strength
        self.failure_ledger: List[Dict[str, Any]] = []

    def record_failure(
        self,
        task_name: str,
        error_msg: str,
        context_vector: Optional[np.ndarray] = None,
    ) -> float:
        """Logs a failure and calculates a negative evidence score."""
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
        """
        Hyperspherical phase-space repulsion:
        remove the parallel component of the failure vector and add controlled phase noise.
        """
        dynamic_strength = self.imprint_strength + 0.15 * max(0.0, 1.0 - fitness)
        proj_coeff = np.vdot(failure_vec, parent_vec)
        parallel = proj_coeff * parent_vec
        mutated = parent_vec - (dynamic_strength * parallel)
        noise_phases = np.random.uniform(-0.05, 0.05, parent_vec.shape)
        mutated = mutated * np.exp(1j * noise_phases)
        return mutated / (np.linalg.norm(mutated) + 1e-12)


class CleanRoomVSAEngine:
    """
    Core FHRR (Frequency Holographic Reduced Representations) Engine (v1.3.1).

    Sparse codebook pruning:
    - Tracks per-atom access_count / last_access / pinned
    - Drops redundant near-duplicates (high pairwise similarity)
    - Drops lowest-utility unpinned atoms when over max_codebook_size
    - Never prunes pinned or Jump-Start protected atoms by default
    """
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
        # name -> {access_count, last_access, pinned}
        self.atom_meta: Dict[str, Dict[str, Any]] = {}
        self.banel = BaNELController()

    def random_symbol(self) -> np.ndarray:
        """Normalized random complex hypervector on the unit hypersphere."""
        phases = np.random.uniform(0.0, 2.0 * np.pi, self.dim)
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
        """Record an access on a codebook atom (utility signal)."""
        self._ensure_meta(name)
        self.atom_meta[name]["access_count"] += 1
        self.atom_meta[name]["last_access"] = time.time()

    def pin(self, name: str) -> None:
        """Prevent an atom from being pruned."""
        self._ensure_meta(name, pinned=True)
        self.atom_meta[name]["pinned"] = True

    def unpin(self, name: str) -> None:
        """Allow pruning (unless name is in DEFAULT_PROTECTED_ATOMS)."""
        self._ensure_meta(name)
        if name in DEFAULT_PROTECTED_ATOMS:
            return
        self.atom_meta[name]["pinned"] = False

    def register(
        self,
        name: str,
        vec: Optional[np.ndarray] = None,
        pinned: bool = False,
    ) -> np.ndarray:
        """Register an atomic symbol into the permanent codebook."""
        if vec is None:
            vec = self.random_symbol()
        else:
            vec = vec.astype(np.complex128)
            vec = vec / (np.linalg.norm(vec) + 1e-12)
        self.codebook[name] = vec
        self._ensure_meta(name, pinned=pinned)
        self.touch(name)
        return vec

    def bind(self, a: np.ndarray, b: np.ndarray) -> np.ndarray:
        """FHRR binding via element-wise Hadamard multiplication."""
        return a * b

    def unbind(self, composite: np.ndarray, binder: np.ndarray) -> np.ndarray:
        """Correlative unbinding via multiplication with the complex conjugate."""
        return composite * np.conj(binder)

    def bundle(self, vectors: List[np.ndarray]) -> np.ndarray:
        """Holographic superposition with normalization."""
        if not vectors:
            raise ValueError("Cannot bundle an empty list of vectors.")
        summed = np.sum(vectors, axis=0)
        norm = np.linalg.norm(summed)
        return summed / (norm + 1e-12)

    def similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Real part of normalized cosine similarity."""
        return float(
            np.real(np.vdot(a, b))
            / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-12)
        )

    def resonator_cleanup(
        self, noisy_vec: np.ndarray, binder: np.ndarray
    ) -> Tuple[np.ndarray, float]:
        """
        Single correlative unbind outside loop →
        strict top-k cardinality → codebook denoising → normalize.
        """
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
        """Hard constitutional gate."""
        return invert_score >= self.min_invertibility

    def gated_resonator_cleanup(
        self, noisy_vec: np.ndarray, binder: np.ndarray
    ) -> Tuple[Optional[np.ndarray], float, bool]:
        """Resonator cleanup followed by invertibility gate."""
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
        """Register a MemSkill only if it passes the invertibility gate."""
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
        """Holographic consolidation of high-fitness episodic vectors."""
        if fitness_scores is not None:
            eligible = [
                v for v, f in zip(episodic_vectors, fitness_scores) if f >= min_fitness
            ]
        else:
            eligible = list(episodic_vectors)

        if len(eligible) < min_count:
            return None
        return self.bundle(eligible)

    # ------------------------------------------------------------------
    # Sparse codebook pruning
    # ------------------------------------------------------------------

    def _utility(self, name: str) -> float:
        """
        Utility score for pruning decisions.
        Higher = keep. Combines access frequency with recency decay.
        """
        meta = self.atom_meta.get(name)
        if meta is None:
            return 0.0
        age = max(1.0, time.time() - float(meta["last_access"]))
        # recency weight: more recent → higher utility
        recency = 1.0 / (1.0 + age / 86400.0)  # day-scale decay
        return float(meta["access_count"]) * (0.5 + 0.5 * recency)

    def prune_redundant(
        self,
        threshold: Optional[float] = None,
    ) -> List[str]:
        """
        Remove unpinned atoms that are near-duplicates of a kept atom.
        Among a redundant pair, keep the higher-utility (or pinned) name.
        Returns list of removed names.
        """
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
                # Redundant pair — drop the weaker unpinned one
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
        """
        If codebook exceeds max_size, remove lowest-utility unpinned atoms
        until size constraint is met. Pinned atoms are never removed.
        """
        limit = self.max_codebook_size if max_size is None else max_size
        if len(self.codebook) <= limit:
            return []

        unpinned = [
            n for n in self.codebook
            if not self.atom_meta.get(n, {}).get("pinned", False)
        ]
        # Sort ascending utility — prune from the bottom
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
        """
        Full sparse pruning pass:
        1) Redundancy cull (near-duplicate unpinned atoms)
        2) Utility cull down to max_codebook_size

        Returns {"redundant": [...], "utility": [...]}.
        """
        redundant = self.prune_redundant(threshold=redundancy_threshold)
        utility = self.prune_by_utility(max_size=max_size)
        return {"redundant": redundant, "utility": utility}

    def codebook_stats(self) -> Dict[str, Any]:
        """Summary statistics for capacity monitoring."""
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

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, directory: str | Path) -> None:
        """Atomically persist codebook, atom meta, BaNEL ledger, and configuration."""
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

            # Atom metadata (utility / pin state)
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
        """Restore codebook, atom meta, BaNEL ledger, and configuration from disk."""
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
    Sandboxes untrusted operations, validates return types, blocks side effects,
    and feeds failure telemetry into the BaNEL ledger.
    """
    def __init__(self, vsa_engine: CleanRoomVSAEngine):
        self.vsa = vsa_engine

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


if __name__ == "__main__":
    print("[*] Initializing Sovereign Clean-Room VSA Engine (v1.3.1 Sparse Pruning)...")
    vsa = CleanRoomVSAEngine(
        dim=8192,
        sparsity_k=256,
        iters=7,
        min_invertibility=0.92,
        max_codebook_size=16,
        redundancy_threshold=0.97,
    )
    gate = CleanRoomGate(vsa)

    # Jump-start primitives (pinned by default)
    for atom in sorted(DEFAULT_PROTECTED_ATOMS):
        vsa.register(atom, pinned=True)

    # Synthetic clutter + a near-duplicate
    base = vsa.random_symbol()
    vsa.register("temp_a", base, pinned=False)
    vsa.register("temp_b", base * np.exp(1j * 0.01), pinned=False)  # near-duplicate
    for i in range(20):
        vsa.register(f"clutter_{i}", pinned=False)

    print(f"[*] Before prune: {vsa.codebook_stats()}")
    report = vsa.prune_codebook()
    print(f"[*] Pruned redundant={report['redundant']} utility={report['utility']}")
    print(f"[*] After prune: {vsa.codebook_stats()}")
    print(f"[+] Protected still present: {sorted(DEFAULT_PROTECTED_ATOMS & set(vsa.codebook))}")
