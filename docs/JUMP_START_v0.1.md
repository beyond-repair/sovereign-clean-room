# Universal Jump-Start v0.1

Cold-start sequence for a new twin identity on the v1.3 constitutional substrate.

**Goal:** Make the twin usable without importing operational history or exposing the host beyond the Clean-Room boundary.

## Sequence

### 1. Substrate & dimension validation

- Import / run `core/clean_room_vsa.py`
- Confirm `dim == 8192`
- Confirm complex128 unit-hypersphere allocation
- Confirm entropy source for `random_symbol()`

### 2. Constitutional parameter lock

Load invariants from `manifests/CONSTITUTION_v1.3.md`:

| Parameter | Value |
|-----------|-------|
| τ_inv (invertibility gate) | 0.92 |
| sparsity_k | 256 |
| resonator iters | 7 |
| isolation C | 0 |

These are **immutable** for Jump-Start v0.1.

### 3. Primitive atom registration

Register orthogonal (near-orthogonal random) base vectors:

| Atom | Role |
|------|------|
| `SELF` | Twin identity anchor |
| `ENVIRONMENT` | External world slot |
| `EPISODIC` | Episodic trace role |
| `SEMANTIC` | Consolidated MemSkill role |
| `SUCCESS` | Positive evidence marker |
| `FAILURE` | BaNEL negative evidence marker |

No domain skills. No network. No Ware physics.

### 4. Atomic persistence verification

- Dry-run `save()` to a temp twin state path
- Confirm `load()` restores codebook atom names
- If cross-volume rename fails, use copy + replace fallback (document in logs)

### 5. Sealed state lockdown

- Freeze base codebook against unauthenticated mutation
- Emit a clean state manifest (atom list + config hash)
- Twin is ready for interaction-history logging only

## Explicit non-goals (v0.1)

- Dream metabolic loop
- HybridCortex / LLM bridges
- Network skills
- Residual-force / free-energy packages

## Exit criteria

Jump-Start v0.1 is complete when:

1. Six primitives are registered and reload after save/load
2. Canonical test harness passes
3. No skill with `network_access: true` is loadable under schema v1.0
