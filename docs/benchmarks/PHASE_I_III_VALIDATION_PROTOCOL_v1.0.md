# SEEM Canonical Validation Protocol v1.0

**Status:** LOCKED protocol revision (2026-09-30)
**Supersedes:** `docs/benchmarks/PHASE_I_III_BENCHMARK_PROTOCOL.md` (research draft)
**Canonical runtime:** `beyond-repair/sovereign-clean-room`
**Network:** `network_access = false`
**Constitution:** v1.3 remains locked. This protocol does not rewrite it.

## Claim classes

A passing check validates only the class it belongs to. It does not validate SEEM as a whole.

| Class | Meaning | May be concluded from |
|---|---|---|
| Benchmark target | Pre-registered number the run is scored against | Nothing. A target is not a result. |
| Hypothesis | Falsifiable statement | A completed run whose analysis matches the pre-registered test |
| Measured result | Value computed from a recorded trial log | The log, the code SHA, and the seed record |
| Implementation guarantee | Property of this repository's code | Review or a deterministic test of that code |
| Research claim | Interpretation beyond the measured substrate property | A separate argument. Not established by this protocol. |

This protocol can establish, when the corresponding run exists: measured FHRR retrieval capacity, resonator convergence, the effect of dimensionality, measured BaNEL failure suppression, route-search efficiency, MemSkill validation reliability, governance fail-closed behavior, cryptographic integrity, and formal/runtime correspondence.

It cannot establish that SEEM possesses a mind, consciousness, general intelligence, subjective experience, or human-equivalent reasoning. Those remain separate hypotheses.

No measured-result cell is filled by this revision. Empty cells stay empty.

## Assumption registry

| ID | Class | Statement |
|---|---|---|
| A1 | User | v1.0 locks the equations and claim split in this file. |
| A2 | Empirical | Invertibility gate `0.92` is already in `manifests/CONSTITUTION_v1.3.md`. |
| A4 | Model | Accuracy threshold `0.95` and bootstrap count `B = 10000` are protocol parameters chosen so `k_max` and intervals are defined. They are not measured facts. |

## 0. Phase 0 — laboratory integrity

Phase I does not start until Phase 0 passes. Phase 0 tests the apparatus, not representation quality.

| ID | Test | Pass condition |
|---|---|---|
| D1 | Deterministic replay | Same seed, code SHA, config, codebook, candidate, and task graph produce identical hypervectors, route probabilities, failure logs, SHACL result, Z3 result, canonical package, hash, and signature payload. |
| D2 | Ledger integrity | Mutating one historical L0 record makes chain validation fail. |
| D3 | Network isolation | An attempted network open fails the run or records an explicit violation. `network_access` remains false. |
| D4 | Signature tampering | One changed byte in a signed package makes `verify` fail. |
| D5 | Governance fail-closed | Disabling SHACL, Z3, or Ed25519 individually yields `REJECT`. A missing signer is `GOVERNANCE_ERROR`, never a mock pass. |

Implementation guarantee already in tree: `core/memskill_governance_gate.py` returns `GATE_3_CRYPTO_UNAVAILABLE` when `skill_crypto` or `SEEM_SKILL_SIGNING_KEY_HEX` is absent. D1–D4 are specified here and are not yet recorded as measured passes.

## 1. Locked substrate

| Parameter | Locked value |
|---|---|
| Primary dimension | `d = 8192` |
| Control dimension | `d = 16384` |
| Codebook size | `M = 1000` |
| Component law | `z_k = exp(i φ_k)`, `φ_k ~ U(-π, π]`, `|z_k| = 1` |
| Binding | `v = ⊙_{i=1}^{k} x_i` (component-wise complex multiply) |
| Resonator bound | `T_max = 7` is a bench bound, not a v1.3 constitution rewrite |
| Trials | `N = 10000` per `(d, k, γ)` |
| Seed record | protocol version, git SHA, config hash, codebook seed, trial index |

### 1.1 Noise model and projection

Additive crosstalk leaves the unit-phasor manifold:

```
v' = v + γ * Σ_{j=1}^{N_noise} n_j
```

`n_j` are unbound codebook vectors. `γ` is the crosstalk weight.

Canonical tested representation is component-wise phasor projection, not vector L2 normalization:

```
π(z)_j = exp(i arg(z_j)) = z_j / |z_j|    if z_j ≠ 0
π(z)_j = undefined                         if z_j = 0
```

A zero component is a trial fault, recorded as `projection_fault`, and excluded from the mean. It is not silently mapped to phase 0.

Vector-level `v' / ||v'||_2` is a different substrate. A run that uses it is not an implementation of this protocol.

`phase(v')` and component-wise `v' / |v'|` are the same operation under this definition. Implementations must call `core.benchmark_metrics.phasor_project`.

## 2. Phase I — representation

### 2.1 Locked invertibility

For unit-magnitude phasors:

```
I(a, â) = (1/d) * Σ_{j=1}^{d} cos(φ_{a,j} - φ_{â,j})
```

`I = 1` for an identical vector. Unrelated random phasors concentrate near 0. This equals `Re(a† â) / d` on the unit-phasor manifold. The cosine-sum form is normative.

### 2.2 Retrieval is a separate measurement

```
ĉ = argmax_{c in C} I(c, a_recovered)
retrieval_hit = 1[ĉ = a]
```

Similarity and retrieval accuracy are both required. `I = 0.94` does not imply the correct symbol was selected.

### 2.3 Capacity definition

`k_max(d, γ)` is the largest `k` in `{2..10}` such that both hold:

- lower bound of the 95% bootstrap CI of mean `I` is `≥ 0.92`
- lower bound of the Clopper-Pearson 95% CI of retrieval accuracy is `≥ 0.95`

If no such `k` exists, `k_max` is undefined for that cell. It is not reported as 0 unless the log explicitly uses that sentinel.

### 2.4 Hypothesis versus target

| ID | Class | Statement |
|---|---|---|
| T1.1 | Target | `k ≥ 6` at `d = 8192`, `T ≤ 7`, mean `I ≥ 0.94` |
| H1.1 | Hypothesis | Under `T ≤ 7`, unbinding remains recoverable at `I ≥ 0.92` for `k ≤ 6` |
| H1.2 | Hypothesis | `R_d = k_max(16384) / k_max(8192) ≥ 1.33` at matched `γ` |

`1.33` is not an architectural expectation. The run reports `R_d`.

| Outcome | Interpretation |
|---|---|
| `R_d ≥ 1.33` | H1.2 supported at that `γ` |
| `1 < R_d < 1.33` | Improvement observed, H1.2 not supported |
| `R_d ≤ 1` | Dimensional scaling did not improve measured capacity |

### 2.5 Required Phase I table

Report every cell. Do not collapse to a single mean.

| d | k | γ | N | mean I | 95% CI | retrieval accuracy | accuracy 95% CI | median T | projection faults |
|---|---|---|---|---|---|---|---|---|---|
| 8192 | 6 | 0 | 10000 | — | — | — | — | — | — |
| 8192 | 6 | 0.1 | 10000 | — | — | — | — | — | — |
| 16384 | 6 | 0.1 | 10000 | — | — | — | — | — | — |

Intervals:

- mean `I`: percentile bootstrap, `B = 10000`, fixed seed, 2.5 and 97.5 percentiles
- retrieval accuracy: Clopper-Pearson 95%

## 3. Phase II — memory / skill layer

Phase II is the interface between representation and BaNEL. It is not a cognition claim.

Required objects:

- positive episodic store (Group B)
- failure evidence store (Groups C and D)
- candidate MemSkill before promotion

No Phase II performance number is claimed in this revision.

## 4. Phase III — BaNEL

### 4.1 Groups

| Group | Retention |
|---|---|
| A | Stateless. No failure retention. |
| B | Positive episodic memory only. |
| C | Structured negative evidence (BaNEL) plus Micro-Dream mutation. |
| D | Negative-memory control. Failure events are retained but assigned to a random route. |

Group D separates "any failure memory helps" from "structured negative evidence helps".

### 4.2 Suppression curve

```
FRR(n) = (repeated failed-route selections after n observed failures of that route)
         / (total route selections)
```

`n` is the failure count already accumulated for the selected route before the selection.

Primary measurement:

```
ΔFRR(n) = FRR_baseline(n) - FRR_BaNEL(n)
```

Baselines are A, B, and D, reported separately. `FRR < 1%` is target T3.1, not the only measurement.

### 4.3 Hypotheses

| ID | Class | Statement |
|---|---|---|
| T3.1 | Target | `FRR < 1.0%` within `N_fail ≤ 2` for Group C |
| T3.2 | Target | Group C reaches a signed MemSkill in `≤ 30%` of the iterations used by unguided MCTS |
| H3.1 | Hypothesis | Group C `FRR(n)` is below Group A and Group D for `n ≥ 1` |
| H3.2 | Hypothesis | Structured negative evidence, not mere failure retention, accounts for the Group C gain versus Group D |

Falsifier retained from the draft: Group C `FRR > 5%` under active BaNEL is BaNEL-amnesia at the target layer. It does not by itself explain the mechanism.

Micro-Dream latency target remains `< 50 ms`. Failure gate `> 100 ms`. Latency is an implementation measurement, not evidence of learning.

## 5. Governance stack

One canonical object feeds every gate.

```
Candidate JSON
      ↓
Canonicalization          core/memskill_ir.py
      ↓
Canonical MemSkill IR
      ├──────────────┐
      ↓              ↓
    SHACL           Z3 encoding satisfiability
      ↓              ↓
      └──────┬───────┘
             ↓
   Cryptographic canonicalization
             ↓
          SHA-256
             ↓
          Ed25519          core/skill_crypto.py
             ↓
       Signed L3 MemSkill
             ↓
      Runtime execution
             ↓
       Observed trace
             ↓
     Trace verification
```

`seem:hasTransitionStep` and `transitions` are not independent inputs. `canonicalize` rejects a candidate whose step multiset differs across those fields.

Signature payload is the canonical IR bytes with the signature field cleared. SHACL, Z3, and Ed25519 therefore attest the same object.

Mock signature rule, normative:

```
skill_crypto unavailable OR signing key absent
        ↓
GOVERNANCE_ERROR
        ↓
REJECT
```

`ED25519_MOCK_SIGNATURE_PASS` is forbidden on this path.

### 5.1 What Z3 establishes

`core/clean_room_z3.py` shows that a symbolic encoding of the candidate is satisfiable or unsatisfiable under the isolate / verify / execute frame and the resource bound.

`SAT` means: there exists a state trajectory satisfying those equations.

`SAT` does not mean: runtime execution of this skill cannot violate the conditions.

The encoding `¬compromised` plus `(¬precondition ⇒ compromised)` makes a violated precondition unsatisfiable. That is a rejection rule for the encoding. It is not an execution semantics proof.

### 5.2 Formal / runtime correspondence

For each candidate, record both labels:

| Z3 encoding | Runtime trace | Interpretation |
|---|---|---|
| SAFE | SAFE | True positive on this pair |
| SAFE | UNSAFE | Formal-model unsoundness |
| UNSAFE | SAFE | Conservative rejection |
| UNSAFE | UNSAFE | Correct rejection |

The SAFE/UNSAFE mismatch is a required outcome column. A Z3 pass count alone is not a safety result.

## 6. Closed loop

```
PHASE 0 integrity
    → PHASE I FHRR / resonator
    → PHASE II memory / skill objects
    → PHASE III BaNEL (A/B/C/D)
    → Micro-Dream candidate
    → canonical IR
    → SHACL and Z3
    → Ed25519
    → runtime execution
    → ledger evidence
    → next cycle
```

Each arrow is independently falsifiable. A pass on one arrow does not transfer.

## 7. Machine-readable result

Schema: `schemas/benchmark_result_v1.json`.

A file that validates against the schema with `status = not_run` is a template. It is not a result. `status = measured` requires `git_sha`, `seed_record`, `trials`, and interval fields.

## 8. Implementation guarantees in this revision

| Guarantee | Evidence |
|---|---|
| Invertibility matches the locked cosine-sum on unit phasors | `core/benchmark_metrics.py` and `tests/test_benchmark_metrics.py` |
| Canonical projection is component-wise phasor projection | same |
| Canonical IR is deterministic and rejects split step lists | `core/memskill_ir.py` |
| Missing signer does not pass | `core/memskill_governance_gate.py` |
| Z3 SAT is labeled as encoding satisfiability | `core/clean_room_z3.py` docstring and this section |

## 9. Not established

- H1.1, H1.2, H3.1, H3.2
- any cell in the Phase I table
- `R_d`
- `ΔFRR(n)`
- formal/runtime correspondence rates
- D1–D4 as executed passes
- mind, consciousness, general intelligence, subjective experience, human-equivalent reasoning
