> **SUPERSEDED RESEARCH DRAFT.** Locked protocol is `PHASE_I_III_VALIDATION_PROTOCOL_v1.0.md`. Do not treat numbers in this draft as measured results or as implementation guarantees. Equation reconstructions here are replaced by the locked cosine-sum definition in v1.0.

# Phase I / Phase III Benchmark Protocol

**Status:** Experimental protocol update (2026-09-30)
**Canonical runtime:** `beyond-repair/sovereign-clean-room`
**Scope:** Phase I (VSA / FHRR representation) and Phase III (BaNEL negative learning)
**Network:** `network_access = false`
**Lineage:** SEEM MemSkill promotion (`R = ⟨S, T, C, V⟩`) under the v1.3 constitution

This protocol establishes reproducible, falsifiable benchmarking for the complex-valued Fourier Holographic Reduced Representation (FHRR) substrate and for Bayesian Negative Evidence Learning (BaNEL) during task execution.

The source paste repeated this block three times. This file is the deduplicated canonical copy.

## Assumption registry

| ID | Class | Statement |
|---|---|---|
| A1 | User | Protocol text as supplied on 2026-09-30 is the update to land. |
| A2 | Empirical | Invertibility gate `0.92` is already locked in `manifests/CONSTITUTION_v1.3.md`. |
| A4 | Model | Equation bodies for `I`, `D_φ`, noise injection, `p_new`, and `FRR` were blank in the source paste. Reconstructed forms below are labeled `RECONSTRUCTED` and are not claimed as the missing source LaTeX. |

## 1. Environment baseline

All experiments run in an isolated, deterministic execution context. No remote service calls.

| Parameter | Value |
|---|---|
| Runtime target | sovereign-clean-room canonical substrate (`network_access = false`) |
| Vector substrate | FHRR over `ℂ^d` |
| Primary dimension | `d = 8192` |
| Control dimension | `d = 16384` |
| Components | `z_k = exp(i φ_k)`, `φ_k ~ U(-π, π]`, `|z_k| = 1` |
| Hardware baseline | Isolated CPU thread, fixed-seed codebook init, local memory, no dynamic heap swelling |
| Ledger | Hash-chained L0 ledger active for post-test audit reconstruction |

Locked constitution invariants that this protocol must not weaken:

- Resonator unbind is single-pass external in v1.3. The `T ≤ 7` loop in H1.1 is a benchmark bound, not a constitution rewrite.
- Invertibility threshold remains `0.92`.
- Core does not take a hard dependency on Z3, rdflib, or pyshacl. Those engines are governance-bench optional (`requirements-governance.txt`).

## 2. Phase I — VSA representation

### 2.1 Hypotheses

- **H1.1 Factor capacity.** An FHRR composite `v = ⊙_{i=1}^{k} x_i` retains unbinding recoverability at invertibility `≥ 0.92` when `k ≤ 6` under `T ≤ 7` resonator iterations.
- **H1.2 Dimensional scaling.** Scaling `d` from `8192` to `16384` reduces phase-crosstalk noise density and increases `k_max` by at least `33%` while keeping clean convergence.

### 2.2 Metrics

**Invertibility / reconstruction quality `I`.** `a` is the target codebook hypervector, `â` is the recovered candidate, `†` is the conjugate transpose.

`RECONSTRUCTED` (A4), consistent with unit-magnitude FHRR and the stated conjugate-transpose form:

```
I(a, â) = |a† â| / d
```

Gate: `I ≥ 0.92`. Target mean: `I ≥ 0.94`.

**Cosine phase distance `D_φ`.** Source body was blank.

`RECONSTRUCTED` (A4):

```
D_φ(a, â) = 1 - Re(a† â) / d
```

**Resonator convergence rate.** Iterations `t ∈ [1, T]` required to reach `I ≥ 0.92`. Bound `T_max = 7`. Non-convergence at `T = 8` is a failure gate.

### 2.3 Protocol

```
Codebook initialization (M symbols)
        ↓
Composite binding (k factors: Role ⊙ Object ⊙ Action ...)
        ↓
Phase noise / crosstalk injection
        ↓
Resonator unbinding loop (T ≤ 7)
        ↓
Invertibility evaluation (I ≥ 0.92 gate)
```

1. **Codebook.** Pre-generate item memory `C = {e_1, ..., e_M}` with `M = 1000` mutually quasi-orthogonal vectors in `ℂ^d`. Fixed seed.
2. **Factor sweep.** For `k ∈ {2, 3, 4, 5, 6, 7, 8, 9, 10}`:
   - Sample `k` distinct codebook vectors.
   - Bind `v = x_1 ⊙ x_2 ⊙ ... ⊙ x_k`.
3. **Crosstalk injection.** Superimpose `N_noise` unbound random codebook vectors. Source equation body was blank.

   `RECONSTRUCTED` (A4), then renormalize onto the unit-magnitude FHRR manifold:

   ```
   v_noisy = normalize( v + γ * Σ_{j=1}^{N_noise} n_j )
   ```

   `γ` is the crosstalk weight in the configuration tuple `(d, k, γ)`.
4. **Resonator.** Pass `v_noisy` to the cleanup memory. Unbind up to `T_max = 7`.
5. **Collection.** `N = 10000` Monte Carlo trials per `(d, k, γ)`. Record accurate symbol retrievals, iterations to converge, and mean `I`.

## 3. Phase III — BaNEL and skill emergence

### 3.1 Hypotheses

- **H3.1 Loop suppression.** BaNEL reduces repeated failure-route selection (`A → failure → A`) to `< 1.0%` within `N_fail ≤ 2` consecutive failure observations, versus a stateless baseline.
- **H3.2 Skill emergence.** On a non-stationary task graph with hidden failure conditions, BaNEL-guided search reaches a valid signed MemSkill `R = ⟨S, T, C, V⟩` in `≤ 30%` of the iterations required by unguided Monte Carlo tree search.

### 3.2 Metrics

**Bayesian route suppression `p_new`.** Source body was blank. `r_i` is a candidate route, `N_fail` is accumulated failure evidence, `α > 0` is the suppression weight.

`RECONSTRUCTED` (A4), then renormalize over the route set:

```
p_new(r_i) = p(r_i) / (1 + α * N_fail(r_i))
Z = Σ_j p_new(r_j)
p_new(r_i) ← p_new(r_i) / Z
```

**Failure recurrence rate.**

`RECONSTRUCTED` (A4):

```
FRR = (selections of a route after that route has already failed)
      / (selections made after at least one failure has been observed)
```

Target: `FRR < 1.0%`. Falsifier: `FRR > 5.0%` under active BaNEL.

**Time-to-validated-MemSkill `T_skill`.** Execution-dream cycles required to pass SHACL structural validation, Z3 constraint verification, and Ed25519 signing.

### 3.3 Protocol

```
Task request input
        ↓
Route candidate selection (p(r_i))
        ↓
Execution environment / mock world
        ↓
Failure observed?
  ├── YES ──→ Log L0 evidence ──→ BaNEL update (p_new) ──→ Micro-Dream mutation
  └── NO  ──→ Pass governance gates (SHACL / Z3 / Ed25519) ──→ Promote L3 MemSkill
```

1. **Task graph.** 100 candidate routes. Seed `80%` with deterministic hidden failures (resource lock, schema mismatch, privilege-boundary breach).
2. **Conditions.**
   - Group A: stateless agent, zero failure retention.
   - Group B: positive episodic memory only.
   - Group C: sovereign-clean-room with BaNEL suppression and Micro-Dream adaptation. Latency target `< 50 ms`. Failure gate `> 100 ms`.
3. **On failure.** Append the raw event to the hash-chained L0 ledger, apply the BaNEL update, emit a mutated route `r_mutated`.
4. **Promotion gate.** Schema completeness, SHACL shape validation, Ed25519 signature of `⟨S, T, C, V⟩` into an L3 MemSkill package. Z3 is the logical gate in front of signing. See `docs/benchmarks/MEMSKILL_GOVERNANCE_PIPELINE.md`.

## 4. Target matrix

| Benchmark parameter | Phase I target | Phase III target | Failure gate |
|---|---|---|---|
| Factor capacity `k` | `k ≥ 6` at `d = 8192` | n/a | `I < 0.92` |
| Resonator iterations `T` | `T ≤ 7` | n/a | non-convergence at `T = 8` |
| Reconstruction quality `I` | mean `I ≥ 0.94` | n/a | `I < 0.92` |
| Failure recurrence rate | n/a | `FRR < 1.0%` | duplicate failure attempt `≥ 2` |
| Micro-Dream latency | n/a | `t_dream < 50 ms` | latency `> 100 ms` |
| MemSkill promotion integrity | n/a | `100%` gate pass | unsigned or malformed skill execution |

These are targets, not measured results. No trial log is attached to this update.

## 5. Falsification

The architecture hypotheses are falsified if any of the following hold during benchmarking:

- **VSA degradation.** Mean factor-unbinding invertibility falls below `0.92` for `k ≤ 5` at `d = 8192`.
- **BaNEL amnesia.** `FRR` exceeds `5.0%` under active BaNEL suppression.
- **Governance bypass.** An unsigned, altered, or constraint-violating route executes without an explicit gate failure in the governance orchestrator or `core/skill_crypto.py`.

## 6. Placement

| Artifact | Path | Role |
|---|---|---|
| This protocol | `docs/benchmarks/PHASE_I_III_BENCHMARK_PROTOCOL.md` | Canonical bench spec |
| Governance pipeline | `docs/benchmarks/MEMSKILL_GOVERNANCE_PIPELINE.md` | SHACL + Z3 + Ed25519 contract |
| SHACL shape | `shapes/mem_skill_shape.ttl` | W3C shape source |
| Offline shape mirror | `shapes/mem_skill_shape.json` | Loadable by `core/clean_room_shacl.py` without rdflib |
| Z3 gate | `core/clean_room_z3.py` | Optional logical verifier |
| Dual-gate orchestrator | `core/memskill_governance_gate.py` | Fail-closed promotion path |

`core/clean_room_shacl.py` is the existing offline SHACL-subset engine. It was not replaced. The supplied `clean_room_shacl.py` orchestrator is landed as `core/memskill_governance_gate.py` so the live engine and its tests stay intact.
