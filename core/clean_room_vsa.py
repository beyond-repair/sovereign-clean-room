#!/usr/bin/env python3
"""Clean-Room VSA Core v1.3.3 — Path A static FHRR engine (operator-authorized)."""
from __future__ import annotations
import hashlib, json, math, time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple, Union
import numpy as np

DEFAULT_DIM = 8192
DEFAULT_SPARSITY_K = 256
DEFAULT_MIN_INVERTIBILITY = 0.92
SPARSITY_STD_THRESHOLD = 1e-6
DEFAULT_PROTECTED_ATOMS: Set[str] = {"SELF","ENVIRONMENT","EPISODIC","SEMANTIC","SUCCESS","FAILURE"}
JUMP_START_V01_ATOMS: Tuple[str, ...] = ("SELF","ENVIRONMENT","EPISODIC","SEMANTIC","SUCCESS","FAILURE")

def _unit_circle(dim: int, rng: np.random.Generator) -> np.ndarray:
    phases = rng.uniform(0, 2 * np.pi, size=dim)
    v = np.exp(1j * phases).astype(np.complex128)
    n = np.linalg.norm(v)
    return (v / n) if n > 1e-12 else v

def _normalize_fhrr(v: np.ndarray) -> np.ndarray:
    v = np.asarray(v, dtype=np.complex128)
    n = np.linalg.norm(v)
    return (v / n).astype(np.complex128) if n >= 1e-12 else v

def _seeded_rng(seed: Optional[int] = None) -> np.random.Generator:
    return np.random.default_rng() if seed is None else np.random.default_rng(int(seed) & 0xFFFFFFFFFFFFFFFF)

@dataclass
class BaNEL:
    failure_ledger: List[Dict[str, Any]] = field(default_factory=list)
    def record_failure(self, label: str, messages: Optional[Union[str, List[str]]] = None, context_vector: Optional[np.ndarray] = None) -> float:
        msg_list = [] if messages is None else ([messages] if isinstance(messages, str) else list(messages))
        self.failure_ledger.append({"label": label, "messages": msg_list, "ts": time.time(),
            "context_norm": float(np.linalg.norm(context_vector)) if context_vector is not None else 0.0})
        return min(1.0, 0.1 * len(self.failure_ledger))

class CleanRoomVSAEngine:
    def __init__(self, dim: int = DEFAULT_DIM, sparsity_k: int = DEFAULT_SPARSITY_K,
                 min_invertibility: float = DEFAULT_MIN_INVERTIBILITY, max_codebook_size: Optional[int] = None,
                 redundancy_threshold: float = 0.98, iters: int = 7, seed: Optional[int] = None):
        self.dim = int(dim); self.sparsity_k = int(sparsity_k)
        self.min_invertibility = float(min_invertibility)
        self.max_codebook_size = max_codebook_size
        self.redundancy_threshold = float(redundancy_threshold)
        self.iters = int(iters); self._rng = _seeded_rng(seed)
        self.codebook: Dict[str, np.ndarray] = {}
        self.metadata: Dict[str, Dict[str, Any]] = {}
        self.atom_meta: Dict[str, Dict[str, Any]] = {}
        self._pinned: Set[str] = set()
        self._utility: Dict[str, float] = {}
        self.banel = BaNEL()
        self._jump_start_seed: Optional[int] = None

    def random_symbol(self, rng: Optional[np.random.Generator] = None) -> np.ndarray:
        return _unit_circle(self.dim, rng if rng is not None else self._rng)
    def random_hv(self, rng: Optional[np.random.Generator] = None) -> np.ndarray:
        return self.random_symbol(rng=rng)
    def bind(self, a: np.ndarray, b: np.ndarray) -> np.ndarray:
        return _normalize_fhrr(a * b)
    def unbind(self, composite: np.ndarray, binder: np.ndarray) -> np.ndarray:
        return _normalize_fhrr(composite * np.conj(binder))
    def bundle(self, vectors: List[np.ndarray], weights: Optional[List[float]] = None) -> np.ndarray:
        if not vectors: raise ValueError("bundle requires at least one vector")
        if weights is None: weights = [1.0] * len(vectors)
        acc = np.zeros(self.dim, dtype=np.complex128)
        for v, w in zip(vectors, weights): acc += w * v
        return _normalize_fhrr(acc)
    def similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        return float(np.real(np.vdot(a, b)))
    def resonator_cleanup(self, noisy: np.ndarray, candidates: List[np.ndarray],
                          sparsity_k: Optional[int] = None, iters: Optional[int] = None) -> Tuple[np.ndarray, int]:
        k = sparsity_k if sparsity_k is not None else self.sparsity_k
        n_iters = iters if iters is not None else self.iters
        x = noisy.copy(); best_idx = -1
        for _ in range(n_iters):
            sims = [self.similarity(x, c) for c in candidates]
            best_idx = int(np.argmax(sims))
            x = _normalize_fhrr(0.7 * x + 0.3 * candidates[best_idx])
            mags = np.abs(x)
            if np.std(mags) > SPARSITY_STD_THRESHOLD:
                idx = np.argsort(mags)[-k:]
                mask = np.zeros_like(mags); mask[idx] = 1.0
                x = _normalize_fhrr(x * mask)
        return x, best_idx

    def register(self, name: str, vec: Optional[np.ndarray] = None, pinned: bool = False,
                 meta: Optional[Dict[str, Any]] = None, binder: Optional[np.ndarray] = None) -> np.ndarray:
        if vec is None: vec = self.random_hv()
        vec = _normalize_fhrr(np.asarray(vec, dtype=np.complex128))
        if binder is not None: vec = self.bind(vec, binder)
        self.codebook[name] = vec
        meta_entry = {"created": time.time(), "pinned": bool(pinned), **(meta or {})}
        self.metadata[name] = meta_entry; self.atom_meta[name] = meta_entry
        self._utility.setdefault(name, 0.0)
        if pinned: self._pinned.add(name)
        else: self._pinned.discard(name)
        return vec
    def add(self, name: str, vec: Optional[np.ndarray] = None, binder: Optional[np.ndarray] = None,
            meta: Optional[Dict[str, Any]] = None, pinned: bool = False) -> np.ndarray:
        return self.register(name, vec=vec, pinned=pinned, meta=meta, binder=binder)
    def get(self, name: str) -> Optional[np.ndarray]:
        return self.codebook.get(name)
    def remove(self, name: str) -> bool:
        if name in self._pinned: return False
        if name in self.codebook:
            del self.codebook[name]
            self.metadata.pop(name, None); self.atom_meta.pop(name, None); self._utility.pop(name, None)
            return True
        return False
    def touch(self, name: str, amount: float = 1.0) -> None:
        if name in self.codebook: self._utility[name] = self._utility.get(name, 0.0) + float(amount)
    def promote_memskill(self, name: str, vec: np.ndarray, binder: Optional[np.ndarray] = None,
                         meta: Optional[Dict[str, Any]] = None) -> bool:
        vec = _normalize_fhrr(np.asarray(vec, dtype=np.complex128))
        if binder is not None:
            recovered = self.unbind(vec, binder)
            best = max((self.similarity(recovered, existing) for existing in self.codebook.values()), default=0.0)
            if best < self.min_invertibility:
                self.banel.record_failure(f"promote_reject:{name}", f"recovered similarity {best:.6f} < {self.min_invertibility}", context_vector=vec)
                return False
        self.add(name, vec=vec, binder=None, meta=meta, pinned=False)
        return True
    def query(self, probe: np.ndarray, top_k: int = 5, min_sim: float = 0.05) -> List[Tuple[str, float]]:
        scores = []
        for name, vec in self.codebook.items():
            s = self.similarity(probe, vec)
            if s >= min_sim:
                scores.append((name, s)); self.touch(name, 0.1)
        scores.sort(key=lambda t: -t[1])
        return scores[:top_k]
    def cleanup_query(self, noisy: np.ndarray, top_k: int = 5) -> List[Tuple[str, float]]:
        cands = list(self.codebook.values())
        if not cands: return []
        cleaned, _ = self.resonator_cleanup(noisy, cands)
        return self.query(cleaned, top_k=top_k)
    def prune_codebook(self, max_size: Optional[int] = None) -> Dict[str, Any]:
        target = max_size if max_size is not None else self.max_codebook_size
        utility_removed = self.prune_by_utility(max_size=target) if target else []
        return {"utility": utility_removed, "redundant": self.prune_redundant()}
    def prune_by_utility(self, max_size: Optional[int] = None) -> List[str]:
        target = max_size if max_size is not None else self.max_codebook_size
        if target is None: return []
        candidates = [n for n in list(self.codebook.keys()) if n not in self._pinned]
        candidates.sort(key=lambda n: self._utility.get(n, 0.0))
        removed: List[str] = []
        while len(self.codebook) > target and candidates:
            name = candidates.pop(0)
            if name in self._pinned: continue
            if self.remove(name): removed.append(name)
        return removed
    def prune_redundant(self) -> List[str]:
        names = list(self.codebook.keys()); removed: List[str] = []
        for i, a in enumerate(names):
            if a not in self.codebook: continue
            for b in names[i + 1:]:
                if b not in self.codebook: continue
                if self.similarity(self.codebook[a], self.codebook[b]) >= self.redundancy_threshold:
                    if a in self._pinned and b in self._pinned: continue
                    victim = b if a in self._pinned else (a if b in self._pinned else b)
                    if victim and self.remove(victim): removed.append(victim)
                    break
        return removed
    def jump_start_v01(self, seed: Optional[int] = 0x5345454D) -> Dict[str, Any]:
        self._jump_start_seed = int(seed) if seed is not None else 0x5345454D
        atoms = []
        for name in JUMP_START_V01_ATOMS:
            atom_seed = int(hashlib.sha256(f"{self._jump_start_seed}:{name}".encode()).hexdigest()[:16], 16)
            vec = _unit_circle(self.dim, _seeded_rng(atom_seed))
            self.register(name, vec=vec, pinned=True, meta={"jump_start": True, "seed": self._jump_start_seed})
            atoms.append(name)
        return {"atoms": atoms, "all_pinned": all(n in self._pinned for n in atoms), "dim": self.dim, "seed": self._jump_start_seed}
    def verify_jump_start_integrity(self) -> bool:
        return all(n in self.codebook and n in self._pinned for n in JUMP_START_V01_ATOMS)

    def codebook_stats(self) -> Dict[str, Any]:
        """Summary for CLI status and dashboards."""
        pinned = sorted(self._pinned)
        return {
            "size": len(self.codebook),
            "pinned": len(pinned),
            "pinned_names": pinned,
            "dim": self.dim,
            "sparsity_k": self.sparsity_k,
            "min_invertibility": self.min_invertibility,
            "jump_start_ok": self.verify_jump_start_integrity(),
            "utility_top": sorted(
                ((n, self._utility.get(n, 0.0)) for n in self.codebook),
                key=lambda t: -t[1],
            )[:10],
        }

    def save(self, path: Union[str, Path]) -> None:
        path = Path(path); path.mkdir(parents=True, exist_ok=True)
        meta = {"dim": self.dim, "sparsity_k": self.sparsity_k, "min_invertibility": self.min_invertibility,
                "max_codebook_size": self.max_codebook_size, "redundancy_threshold": self.redundancy_threshold,
                "jump_start_seed": self._jump_start_seed, "pinned": sorted(self._pinned), "utility": self._utility,
                "metadata": {k: {kk: vv for kk, vv in v.items() if not isinstance(vv, np.ndarray)} for k, v in self.metadata.items()}}
        (path / "engine_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        for name, vec in self.codebook.items():
            np.savez_compressed(path / f"hv_{name}.npz", real=np.real(vec).astype(np.float64), imag=np.imag(vec).astype(np.float64))
        (path / "codebook_index.json").write_text(json.dumps(list(self.codebook.keys())), encoding="utf-8")
    def load(self, path: Union[str, Path]) -> None:
        path = Path(path)
        meta = json.loads((path / "engine_meta.json").read_text(encoding="utf-8"))
        self.dim = int(meta["dim"]); self.sparsity_k = int(meta["sparsity_k"])
        self.min_invertibility = float(meta.get("min_invertibility", DEFAULT_MIN_INVERTIBILITY))
        self.max_codebook_size = meta.get("max_codebook_size")
        self.redundancy_threshold = float(meta.get("redundancy_threshold", 0.98))
        self._jump_start_seed = meta.get("jump_start_seed")
        self._pinned = set(meta.get("pinned", [])); self._utility = {k: float(v) for k, v in meta.get("utility", {}).items()}
        self.metadata = meta.get("metadata", {}); self.atom_meta = dict(self.metadata); self.codebook = {}
        index_path = path / "codebook_index.json"
        names = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else [p.stem[3:] for p in path.glob("hv_*.npz")]
        for name in names:
            f = path / f"hv_{name}.npz"
            if not f.exists(): continue
            data = np.load(f)
            self.codebook[name] = (data["real"] + 1j * data["imag"]).astype(np.complex128)
            if name not in self.atom_meta:
                self.atom_meta[name] = {"pinned": name in self._pinned}; self.metadata[name] = self.atom_meta[name]

class CleanRoomGate:
    def __init__(self, engine: CleanRoomVSAEngine, trusted_verify_keys: Optional[Sequence[str]] = None,
                 require_skill_signature: bool = False, enable_shacl: bool = False, **_kwargs: Any):
        self.engine = engine
        self.trusted_verify_keys: List[str] = list(trusted_verify_keys or [])
        self.require_skill_signature = bool(require_skill_signature)
        self.enable_shacl = bool(enable_shacl)
    def add_trusted_verify_key(self, key_hex: str) -> None:
        if key_hex and key_hex not in self.trusted_verify_keys: self.trusted_verify_keys.append(key_hex)
    def execute_skill_package(self, package: Dict[str, Any], handler: Callable[..., Any], *args: Any, **kwargs: Any) -> Dict[str, Any]:
        try:
            sov = package.get("sovereignty") or {}
            if sov.get("network_access") is True:
                evidence = self.engine.banel.record_failure("network_access_denied", "network_access=true forbidden in clean room")
                return {"status": "FAIL", "output": None, "error": "network_access not permitted in Clean-Room", "banel_evidence": evidence}
            if self.require_skill_signature:
                try:
                    from skill_crypto import verify_package, is_placeholder_signature
                except ImportError:
                    from core.skill_crypto import verify_package, is_placeholder_signature  # type: ignore
                sig = (package.get("manifest") or {}).get("signature")
                if is_placeholder_signature(sig):
                    evidence = self.engine.banel.record_failure("signature_placeholder", "unsigned or placeholder signature")
                    return {"status": "FAIL", "output": None, "error": "signature missing or placeholder", "banel_evidence": evidence}
                if not self.trusted_verify_keys:
                    evidence = self.engine.banel.record_failure("no_trust_root", "empty trusted verify key store")
                    return {"status": "FAIL", "output": None, "error": "no trusted verify keys configured", "banel_evidence": evidence}
                try:
                    verify_package(package, self.trusted_verify_keys)
                except Exception as e:
                    evidence = self.engine.banel.record_failure("signature_fail", str(e))
                    return {"status": "FAIL", "output": None, "error": f"signature verification failed: {e}", "banel_evidence": evidence}
            output = handler(*args, **kwargs) if callable(handler) else handler
            return {"status": "PASS", "output": output, "error": None, "banel_evidence": 0.0}
        except Exception as e:
            evidence = self.engine.banel.record_failure("skill_exception", str(e))
            return {"status": "FAIL", "output": None, "error": str(e), "banel_evidence": evidence}
    def execute_sandboxed_computation(self, label: str, fn: Callable[[], Any]) -> Dict[str, Any]:
        try:
            result = fn()
            arr = np.asarray(result)
            if arr.dtype.kind in "fc" and not np.isfinite(arr).all():
                evidence = self.engine.banel.record_failure(label, "non-finite values in result")
                return {"status": "FAIL", "output": None, "error": "non-finite values", "banel_evidence": evidence}
            return {"status": "PASS", "output": result, "error": None, "banel_evidence": 0.0}
        except Exception as e:
            evidence = self.engine.banel.record_failure(label, str(e))
            return {"status": "FAIL", "output": None, "error": str(e), "banel_evidence": evidence}

__all__ = ["CleanRoomVSAEngine", "CleanRoomGate", "DEFAULT_PROTECTED_ATOMS", "JUMP_START_V01_ATOMS", "DEFAULT_DIM", "DEFAULT_SPARSITY_K", "BaNEL"]
