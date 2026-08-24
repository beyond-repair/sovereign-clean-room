        if vec is None:
            vec = self.random_hv()
        vec = _normalize_fhrr(vec)
        if binder is not None:
            vec = self.bind(vec, binder)
        self.codebook[name] = vec
        self.metadata[name] = {
            "created": time.time(),
            "pinned": bool(pinned),
            **(meta or {}),
        }
        if pinned:
            self._pinned.add(name)
        return vec

    def get(self, name: str) -> Optional[np.ndarray]:
        return self.codebook.get(name)

    def remove(self, name: str) -> bool:
        if name in self._pinned:
            return False
        if name in self.codebook:
            del self.codebook[name]
            self.metadata.pop(name, None)
            return True
        return False

    def promote_memskill(
        self,
        name: str,
        vec: np.ndarray,
        binder: Optional[np.ndarray] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> np.ndarray:
        """Fast path: store without full resonator; used by MemSkill evolution."""
        return self.add(name, vec=vec, binder=binder, meta=meta, pinned=False)

    def query(
        self,
        probe: np.ndarray,
        top_k: int = 5,
        min_sim: float = 0.05,
    ) -> List[Tuple[str, float]]:
        scores = []
        for name, vec in self.codebook.items():
            s = self.similarity(probe, vec)
            if s >= min_sim:
                scores.append((name, s))
        scores.sort(key=lambda t: -t[1])
        return scores[:top_k]

    def cleanup_query(
        self,
        noisy: np.ndarray,
        top_k: int = 5,
    ) -> List[Tuple[str, float]]:
        cands = list(self.codebook.values())
        names = list(self.codebook.keys())
        if not cands:
            return []
        cleaned, idx = self.resonator_cleanup(noisy, cands)
        # re-score against cleaned
        return self.query(cleaned, top_k=top_k)
