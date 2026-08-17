# Post-Audit Roadmap (Panel Review v1.0)

**Status:** Theory expansion frozen. Implementation and empirical validation only.
**Invariant:** Constitutional substrate v1.3 remains unchanged.

## Risk mitigation matrix

| Audit axis | Finding | Risk | Action |
|------------|---------|------|--------|
| Algebra & capacity (E1) | Phase drift avoided; capacity at D=8192 unmeasured | Medium | Capacity / false-reject benchmark suite |
| Cognitive mechanics (E2) | Dream loop not on v1.3 | High | Freeze Dream claims; schema-driven MemSkill promotion first |
| Reliability (E3) | rename same-volume; tolerances uncalibrated | Medium | Calibrate bounds; copy-fallback for cross-volume |
| Sovereignty (E4, E6) | Core offline; skills reintroduce risk | High | Signed manifests; no Ware physics in core |
| Product hygiene (E5) | Legacy overclaims; cold-start gap | High | Jump-Start v0.1; claims ≤ locked core |

## Ordered phases

1. Skill-package schema (`schemas/skill_package_v1.json`)
2. Universal Jump-Start v0.1 (`docs/JUMP_START_v0.1.md`)
3. Empirical harness (`tests/test_canonical_v13.py`)

## Locked v1.3 parameters (do not drift)

| Parameter | Value |
|-----------|-------|
| Dimension D | 8192 |
| Invertibility gate τ | 0.92 |
| Sparsity cardinality k | **256** |
| Resonator iterations | 7 |
| Isolation coefficient C | 0 (block-system) |
