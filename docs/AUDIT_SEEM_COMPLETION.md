# SEEM completion-pass audit

Engineering audit of `beyond-repair/sovereign-clean-room` at the start of branch `seem-completion-pass` (base `4cf555704c92eded759cb9690e6f028f51b40913`). This is not a consciousness, sentience, or general-intelligence claim.

## What is canonical

| Artifact | Status |
|---|---|
| `manifests/CONSTITUTION_v1.3.md` | Locked. Not modified. |
| `docs/benchmarks/PHASE_I_III_VALIDATION_PROTOCOL_v1.0.md` | Locked measurement protocol. Supersedes the draft. |
| `docs/benchmarks/PHASE_I_III_BENCHMARK_PROTOCOL.md` | Superseded research draft. Reconstructed equations are not normative. |
| `core/benchmark_metrics.py` | Locked cosine-sum `I` and `phasor_project`. |
| `core/clean_room_vsa.py` | Constitution runtime. Unit-hypersphere L2 algebra. Still the path used by the CLI, orchestrator, episodic store, and v1.3 tests. |
| `core/memskill_governance_gate.py` | Promotion path: canonical IR, SHACL, Z3, Ed25519. Fail-closed. |
| `core/clean_room_shacl.py` | Offline shape subset. Not the Turtle gate. |
| `core/memskill.py` | Older episode-to-package promotion. Placeholder signature is not a governance pass. |

Git history: `8f182a4` added the Phase I/III protocol and governance gates. `4cf5557` locked v1.0 and split claim classes. No commit before this branch contains a k_max trial log.

## Intended pipeline vs code before this pass

```
Input/Experience → Evidence → Memory → Candidate MemSkill → Canonical IR
  → SHACL → Z3 → Cryptographic Signing → L3/Executable Skill → Runtime
  → Observed Trace → Verification → Success/Failure Evidence → Evolution
```

| Stage | Before this pass | Deviation |
|---|---|---|
| Input | CLI, orchestrator handlers, episodic atoms | No single pipeline object |
| Evidence | `CleanRoomLedger` hash chain; `TaskAtom` ledger | Ledger did not expose a forensic field map or duplicate/gap/order report |
| Memory | Episodic vector store and TaskAtoms | No explicit evidence-vs-inference lifecycle, supersession, or corruption check on a skill memory |
| Candidate MemSkill | Governance candidate JSON and a separate episode package | Two representations. Episode promotion could emit `UNSIGNED_DEV_PLACEHOLDER` |
| Canonical IR | `canonicalize` compared transition lists with `==` | Reordered copies of the same steps were rejected. Multiset rule was specified, not implemented. Preconditions, targets, and duplicate `stepIndex` were not checked |
| SHACL | Turtle shape, closed | `rdf:type` on a transition step failed the closed shape, so a well-formed candidate could not pass Gate 1 |
| Z3 | Isolate / verify / execute and resource sum | Did not encode declared preconditions. SAT was already documented as not runtime safety. No runtime interpreter, so the correspondence matrix was untested |
| Signing | Ed25519 over canonical package bytes | Gate 3 existed. Phase 0 D4/D5 were not executed as tests |
| L3 runtime | `CleanRoomGate.execute_skill_package` | Package execution is not the Z3 trace semantics |
| Trace / verification | Gate status strings | No SAFE/UNSAFE correspondence record |
| Failure evidence | `BaNEL.record_failure` appends a label | No route-level FRR, no groups A–D, no structured vs scrambled assignment. Constitution names hyperspherical parallel repulsion; the class did not implement it |
| Evolution | Not a closed loop | No Micro-Dream grounded in existing route evidence |

Phase I runner was absent. `k_max` existed only as a function over caller-supplied CI bounds. Schema `schemas/benchmark_result_v1.json` had no `partial` status, so an incomplete grid could not be recorded without pretending `measured` or leaving the file as a schema.

VSA binding is component-wise multiply followed by vector L2 normalization. The locked protocol forbids that normalization for the measured substrate and requires `z_k = exp(i φ_k)` with component-wise phasor projection. Those are different substrates. This pass does not rewrite the constitution algebra. Measurements go through `core/fhrr_protocol.py`.

`network_access=false`, invertibility floor 0.92, fail-closed gates, Ed25519, and canonical hashing were not relaxed.

## Repairs in this pass

- Protocol runner: unit phasors on `(-π, π]`, component-wise bind, noise `v' = v + γ Σ n_j` with recorded `N_noise=1`, `phasor_project`, cosine-sum `I`, argmax retrieval stored separately from `I`.
- Resonator: sequential soft codebook cleanup, random unit-phasor init, stop on a repeated argmax tuple or `T_max=7`. Commutative binding aligns the scored slot by invertibility to the designated factor. This is an implementation choice recorded in the configuration hash, not a hidden protocol constant.
- IR multiset check, canonical `stepIndex` order, duplicate index rejection, precondition and target checks.
- Z3 precondition discharge. `dischargedBy=EXTERNAL` is unsat in the encoding.
- Runtime trace and correspondence labels.
- Offline boundary refuses a connection before any socket call.
- BaNEL groups A–D, route-level `FRR(n)`, supersession, Micro-Dream from existing routes only.
- Memory lifecycle log. Ledger forensic view and anomaly report.
- `parallel_repulsion` on the constitution BaNEL object.
- SHACL shapes ignore `rdf:type` so a typed step can be closed without dropping the other constraints.
- Schema status enum includes `partial`.
- `pytest.ini` puts `core` on the path. Several tests imported `core` modules with no path entry; CI would not have collected them.

## Not established

H1.1, H1.2, H3.1, H3.2, any full `N=10000` cell, `k_max`, `R_d`, and any claim of mind, consciousness, sentience, or general intelligence.

Measured numbers, if any, live only in `results/execution_record.json` after `scripts/run_completion_measurements.py`. Cells that were not executed have status `not_run` and null metrics.

## Measured this session

Code SHA `c691bb6a19b2764fc0b3f9cd85d091d3df49ad7c`. Source: `results/execution_record.json`. These are partial runs, not protocol completion.

Phase I prefix, M=1000, N_noise=1, bootstrap B=10000. Wall clock 15.178s for 11 trials. `k_max` is null at every executed (d, γ). `R_d` is null.

| d | k | γ | N completed | mean I | I 95% CI | accuracy | accuracy 95% CI | median T | faults | status |
|---|---|---|---|---|---|---|---|---|---|---|
| 8192 | 2 | 0 | 4 | 0.3299038379176722 | [0.08757042727644915, 0.5722372485588954] | 0.75 | [0.19412044968324343, 0.9936905367902902] | 3 | 0 | partial |
| 8192 | 2 | 0.1 | 4 | 0.3166902291446315 | [0.0874713279407179, 0.5459091303485452] | 0.75 | [0.19412044968324343, 0.9936905367902902] | 3 | 0 | partial |
| 8192 | 3 | 0 | 2 | 0.024250546334238832 | [0.020666484985028058, 0.027834607683449607] | 0.0 | [0.0, 0.841886116991581] | 6 | 0 | partial |
| 16384 | 2 | 0.1 | 1 | -0.02366869718172837 | [-0.02366869718172837, -0.02366869718172837] | 0.0 | [0.0, 0.9750000000000001] | 5 | 0 | partial |

32 other (d, k, γ) cells are `not_run`. None use N=10000.

Phase III, one seed `20261001`, 100 routes, 80 failing, 500 selections. Status partial. Route-level FRR:

| group | FRR(1) | FRR(2) |
|---|---|---|
| A | 0.156 | 0.142 |
| B | 0.126 | 0.078 |
| C | 0.152 | 0.14 |
| D | 0.146 | 0.136 |

ΔFRR = baseline − C is about +0.004 / +0.002 for A, −0.026 / −0.062 for B, and −0.006 / −0.004 for D. That does not establish H3.1 or H3.2. Group C FRR is not below 1%. Micro-Dream ran 305 times in group C; median latency in that run was 0.017365999838148127 ms. The separate timing loop measured median Micro-Dream at 0.0023069999315339373 ms. Both are under 100 ms in this process. Latency is not evidence of learning.

No hypothesis in the locked protocol is established.
