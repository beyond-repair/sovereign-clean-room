#!/usr/bin/env python3
"""
Hyperdimensional Episodic Memory Store — offline FHRR recall.

- File-backed episode vectors (complex128, dim=8192)
- Role-filler binding with constitutional EPISODIC atom when present
- Superposition bundles for multi-trace summaries
- Similarity search with locked threshold τ=0.92
- No external DB, no network
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np

from clean_room_vsa import CleanRoomVSAEngine

DEFAULT_TAU = 0.92


@dataclass
class MemoryHit:
    episode_id: str
    similarity: float
    meta: Dict[str, Any]
    vector: np.ndarray


class EpisodicMemoryStore:
    """
    Local episodic store on top of CleanRoomVSAEngine algebra.

    Layout:
      root/
        manifest.json
        episodes/
          <episode_id>.npy
        bundles/
          <bundle_id>.npy
    """

    def __init__(
        self,
        root: Union[str, Path],
        engine: Optional[CleanRoomVSAEngine] = None,
        tau: float = DEFAULT_TAU,
    ):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.episodes_dir = self.root / "episodes"
        self.bundles_dir = self.root / "bundles"
        self.episodes_dir.mkdir(exist_ok=True)
        self.bundles_dir.mkdir(exist_ok=True)
        self.manifest_path = self.root / "manifest.json"

        self.engine = engine or CleanRoomVSAEngine(dim=8192)
        if self.engine.dim != 8192:
            raise ValueError("EpisodicMemoryStore requires dim=8192")
        if not (0.0 < tau <= 1.0):
            raise ValueError("tau must be in (0, 1]")
        self.tau = float(tau)

        self.manifest: Dict[str, Any] = {
            "version": "episodic_memory_v1",
            "dim": 8192,
            "tau": self.tau,
            "episodes": {},
            "bundles": {},
        }
        if self.manifest_path.is_file():
            self.manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            self.tau = float(self.manifest.get("tau", self.tau))

    def _save_manifest(self) -> None:
        self.manifest["tau"] = self.tau
        self.manifest["dim"] = 8192
        tmp = self.manifest_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.manifest, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(self.manifest_path)

    @staticmethod
    def _safe_id(episode_id: str) -> str:
        return "".join(c if c.isalnum() or c in "-_" else "_" for c in episode_id)[:128]

    def _note_filler(self, text: str) -> np.ndarray:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        seed = int.from_bytes(digest[:8], "big") % (2**32 - 1)
        rng = np.random.default_rng(seed)
        return self.engine.random_symbol(rng=rng)

    def encode_episode(
        self,
        content: str,
        bind_to_episodic_role: bool = True,
    ) -> np.ndarray:
        """Map text → FHRR vector; optionally bind EPISODIC ⊙ filler."""
        filler = self._note_filler(content)
        if bind_to_episodic_role and "EPISODIC" in self.engine.codebook:
            role = self.engine.codebook["EPISODIC"]
            return self.engine.bind(role, filler)
        return filler

    def remember(
        self,
        content: str,
        episode_id: Optional[str] = None,
        meta: Optional[Dict[str, Any]] = None,
        bind_to_episodic_role: bool = True,
    ) -> str:
        """Persist a new episodic trace. Returns episode_id."""
        if not content or not str(content).strip():
            raise ValueError("content must be non-empty")

        eid = episode_id or hashlib.sha256(
            f"{content}|{time.time_ns()}".encode("utf-8")
        ).hexdigest()[:16]
        eid = self._safe_id(eid)

        vec = self.encode_episode(content.strip(), bind_to_episodic_role=bind_to_episodic_role)
        path = self.episodes_dir / f"{eid}.npy"
        np.save(path, vec)

        self.manifest["episodes"][eid] = {
            "path": str(path.name),
            "meta": meta or {},
            "content_preview": content.strip()[:200],
            "created_at": time.time(),
            "bound_episodic": bool(
                bind_to_episodic_role and "EPISODIC" in self.engine.codebook
            ),
        }
        self._save_manifest()

        if "SUCCESS" in self.engine.codebook:
            self.engine.touch("SUCCESS")
        return eid

    def load_vector(self, episode_id: str) -> np.ndarray:
        eid = self._safe_id(episode_id)
        info = self.manifest["episodes"].get(eid)
        if not info:
            raise KeyError(f"unknown episode_id: {episode_id}")
        return np.load(self.episodes_dir / info["path"]).astype(np.complex128)

    def similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        return self.engine.similarity(a, b)

    def recall(
        self,
        query: str,
        top_k: int = 5,
        tau: Optional[float] = None,
        bind_to_episodic_role: bool = True,
    ) -> List[MemoryHit]:
        """
        Similarity search over stored episodes.
        Hits require similarity >= tau (default store.tau = 0.92).
        """
        threshold = self.tau if tau is None else float(tau)
        q = self.encode_episode(query, bind_to_episodic_role=bind_to_episodic_role)
        hits: List[MemoryHit] = []

        for eid, info in self.manifest.get("episodes", {}).items():
            vec = np.load(self.episodes_dir / info["path"]).astype(np.complex128)
            sim = self.similarity(q, vec)
            if sim >= threshold:
                hits.append(
                    MemoryHit(
                        episode_id=eid,
                        similarity=sim,
                        meta=dict(info.get("meta") or {}),
                        vector=vec,
                    )
                )

        hits.sort(key=lambda h: h.similarity, reverse=True)
        return hits[: max(1, top_k)]

    def best_match(
        self,
        query: str,
        tau: Optional[float] = None,
    ) -> Optional[MemoryHit]:
        hits = self.recall(query, top_k=1, tau=tau)
        return hits[0] if hits else None

    def bundle_episodes(
        self,
        episode_ids: Sequence[str],
        bundle_id: Optional[str] = None,
    ) -> str:
        """Superpose episode vectors into a normalized holographic bundle."""
        vectors = [self.load_vector(eid) for eid in episode_ids]
        if not vectors:
            raise ValueError("no episodes to bundle")
        bundled = self.engine.bundle(list(vectors))
        bid = bundle_id or hashlib.sha256(
            ("|".join(episode_ids)).encode("utf-8")
        ).hexdigest()[:16]
        bid = self._safe_id(bid)
        np.save(self.bundles_dir / f"{bid}.npy", bundled)
        self.manifest.setdefault("bundles", {})[bid] = {
            "members": list(episode_ids),
            "created_at": time.time(),
        }
        self._save_manifest()
        return bid

    def unbind_probe(
        self,
        episode_id: str,
        content: str,
    ) -> Tuple[float, bool]:
        """
        If episode was stored as EPISODIC ⊙ filler(content), recover filler
        and score invertibility vs content-derived filler. Returns (score, pass).
        """
        if "EPISODIC" not in self.engine.codebook:
            raise RuntimeError("EPISODIC role missing — run jump_start_v01()")
        bound = self.load_vector(episode_id)
        role = self.engine.codebook["EPISODIC"]
        recovered = self.engine.unbind(bound, role)
        expected = self._note_filler(content.strip())
        score = self.similarity(recovered, expected)
        return score, score >= self.tau

    def list_episodes(self) -> List[str]:
        return sorted(self.manifest.get("episodes", {}).keys())

    def stats(self) -> Dict[str, Any]:
        return {
            "episodes": len(self.manifest.get("episodes", {})),
            "bundles": len(self.manifest.get("bundles", {})),
            "tau": self.tau,
            "dim": 8192,
            "root": str(self.root),
        }
