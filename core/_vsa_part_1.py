        return _normalize_fhrr(composite * np.conj(binder))

    def bundle(self, vectors: List[np.ndarray], weights: Optional[List[float]] = None) -> np.ndarray:
        if not vectors:
            raise ValueError("bundle requires at least one vector")
        if weights is None:
            weights = [1.0] * len(vectors)
        acc = np.zeros(self.dim, dtype=np.complex128)
        for v, w in zip(vectors, weights):
            acc += w * v
        return _normalize_fhrr(acc)

    def similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        return float(np.real(np.vdot(a, b)) / self.dim)

    def resonator_cleanup(
        self,
        noisy: np.ndarray,
        candidates: List[np.ndarray],
        sparsity_k: Optional[int] = None,
        iters: int = 7,
    ) -> Tuple[np.ndarray, int]:
        """Single-pass-style resonator with magnitude-aware sparsity guard.

        On pure unit-circle FHRR vectors, |mag| std is ~0, so we skip hard
        top-k sparsity to preserve exact binds. Only project when the vector
        has drifted (std(|mag|) > SPARSITY_STD_THRESHOLD).
        """
        k = sparsity_k if sparsity_k is not None else self.sparsity_k
        x = noisy.copy()
        best_idx = -1
        best_sim = -1.0
        for _ in range(iters):
            # find best candidate
            sims = [self.similarity(x, c) for c in candidates]
            best_idx = int(np.argmax(sims))
            best_sim = sims[best_idx]
            # soft attract toward winner
            x = _normalize_fhrr(0.7 * x + 0.3 * candidates[best_idx])
            # sparsity guard: only hard-project when magnitudes have spread
            mags = np.abs(x)
            if np.std(mags) > SPARSITY_STD_THRESHOLD:
                idx = np.argsort(mags)[-k:]
                mask = np.zeros_like(mags)
                mask[idx] = 1.0
                x = _normalize_fhrr(x * mask)
        return x, best_idx

    # ------------------------------------------------------------------
    # Codebook / memory
    # ------------------------------------------------------------------
    def add(
        self,
        name: str,
        vec: Optional[np.ndarray] = None,
        binder: Optional[np.ndarray] = None,
        meta: Optional[Dict[str, Any]] = None,
        pinned: bool = False,
    ) -> np.ndarray:
