# MemSkill Governance Pipeline

**Status:** Update 2026-09-30
**Applies to:** candidate MemSkill `R = ⟨S, T, C, V⟩` before `core/skill_crypto.py` signing
**Fail-closed:** a gate error is a rejection, never a promotion

Candidate MemSkills must pass structural governance and logical verification before signing.

- **Structural governance (SHACL).** Graph topology, required metadata, type constraints, array length bounds.
- **Logical verification (Z3).** Precondition satisfaction, resource non-conflict, safety bounds, state-invariant preservation.

## Pipeline

```
Candidate MemSkill JSON/RDF
            │
            ▼
┌───────────────────────────┐
│   SHACL Structural Gate   │ ──(Violations Found)──► REJECT / MUTATE
└───────────┬───────────────┘
            │ PASS
            ▼
┌───────────────────────────┐
│  Z3 Formal Solver Gate    │ ──(Unsatisfiable)─────► REJECT / BaNEL LOG
└───────────┬───────────────┘
            │ SAT / PROVED
            ▼
┌───────────────────────────┐
│  Ed25519 Signing Module   │
└───────────┬───────────────┘
            │
            ▼
   Signed L3 MemSkill
```

## Landed modules

| Source name in the update | Landed path | Why |
|---|---|---|
| `mem_skill_shape.ttl` | `shapes/mem_skill_shape.ttl` | New shape. No prior Turtle shape in this repo. |
| `clean_room_z3.py` | `core/clean_room_z3.py` | New. Lazy-imports `z3` so core CI does not require it. |
| `clean_room_shacl.py` orchestrator | `core/memskill_governance_gate.py` | Existing `core/clean_room_shacl.py` is the locked offline subset engine used by `tests/test_shacl_engine.py`. Overwrite rejected. |

## Deviation from the supplied orchestrator

The supplied `evaluate_and_sign` fell back to `signature = "ED25519_MOCK_SIGNATURE_PASS"` when `core.skill_crypto` was missing, and still returned success.

That fallback is a governance bypass under section 5 of the Phase I/III protocol. The landed orchestrator does not treat a mock stamp as a pass.

- Real signing uses `core.skill_crypto.sign_package` when `SEEM_SKILL_SIGNING_KEY_HEX` is set and the candidate has a `manifest`.
- If the signer or key is absent, the function returns `passed = false` and `GATE_3_CRYPTO_UNAVAILABLE`.
- `rdflib` / `pyshacl` absence returns `GATE_1_SHACL_ERROR`, not a pass.

Optional dependencies live in `requirements-governance.txt`. They are not added to `requirements.txt` because the v1.3 constitution forbids heavy external frameworks in the core path, and CI installs only `requirements.txt`.

## Operational invariant matrix

| Verification tier | Engine | Target invariant | Fail-closed action |
|---|---|---|---|
| Data resiliency | SHACL shape | `networkAccessPermitted == false` | Reject. Flag security policy alert in the L0 ledger. |
| Substrate invertibility | SHACL shape | `invertibilityScore >= 0.92` | Reject. Trigger Micro-Dream parameter optimization. |
| Resource bound | Z3 solver | `Σ Cost_i ≤ 100` | Reject. Route to BaNEL negative-learning log. |
| Precondition safety | Z3 solver | `EXECUTE ⇒ (ISOLATE ∧ VERIFY)` | Abort path. Decrease route probability `p(r_i)`. |
| Cryptographic provenance | Ed25519 | Signature over canonical JSON SHA-256 | Refuse execution in the runtime orchestrator. |

## Shape constraints (normative summary)

Root shape `seem:MemSkillShape`, closed, ignores `seem:comment`.

| Path | Constraint |
|---|---|
| `seem:skillId` | UUIDv4 string, count 1 |
| `seem:invertibilityScore` | float in `[0.92, 1.0]`, count 1 |
| `seem:maxExecutionMs` | integer in `[1, 5000]`, count 1 |
| `seem:networkAccessPermitted` | boolean, `hasValue false`, count 1 |
| `seem:hasTransitionStep` | `seem:TransitionStepShape`, count in `[1, 16]` |
| `seem:verificationHash` | SHA-256 hex, count 1 |

Transition step shape, closed:

| Path | Constraint |
|---|---|
| `seem:stepIndex` | integer `≥ 0`, count 1 |
| `seem:operatorSymbol` | `^[A-Z0-9_]+$`, count 1 |
| `seem:resourceCost` | integer in `[0, 100]`, count 1 |

Namespace: `http://adl-seem.org/core/ontology#`.

## Z3 obligations

`MemSkillZ3Verifier` (`max_resource_capacity = 100` default):

1. Each step cost is the declared non-negative integer. Cumulative cost `≤ C_max`.
2. Compromised state is forbidden on every index.
3. Operator frame:
   - `ISOLATE_ENVIRONMENT` sets isolated.
   - `VERIFY_INTEGRITY` requires isolated, else compromised.
   - `EXECUTE_PRIMITIVE` requires isolated and verified, else compromised.
   - Other operators are frame-preserving.
4. Postcondition: final state is verified.

`sat` is necessary, not a substitute for the Ed25519 gate. The encoding forces preconditions by asserting `¬compromised` together with `¬precondition ⇒ compromised`. An unsat result is a rejection, not a proof of a specific violated step, unless the caller extracts an unsat core.

## Pending validation

- No Monte Carlo log for H1.1, H1.2, H3.1, or H3.2 is in this update.
- Z3 and pyshacl are not in the default CI image. `tests/test_memskill_z3_gate.py` skips when `z3` is absent.
- Reconstructed metric bodies in the protocol remain A4 until the source equations are supplied.
