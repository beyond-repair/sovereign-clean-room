# Portfolio governance

Canonical offline SEEM / Clean-Room runtime for the beyond-repair portfolio. Primary class: **ACTIVE**. Authoritative implementation named in ADL-Governance `docs/CANONICAL_REPOS.md`. This file does not amend `manifests/CONSTITUTION_v1.3.md`.

Parent rules, quoted from ADL-Governance `main` (`c2f677ff9613fc2c9614535b1bb34e1b3d8857ed`):

- `docs/CONSTITUTION.md` Article 2: "Every repository MUST carry exactly one primary class."
- Article 4: "Physical and cognitive performance claims MUST be tagged Level 0–5 per CLAIM_VALIDATION.md. Cryptographic or CI success does **not** imply experimental physics validation."
- Article 5: "Physics modules are hypothesis-grade; offline only."
- `docs/CLAIM_VALIDATION.md`: "Default for Ware/CFT/IQG/Coherence Drive content: **Level 1** unless higher is evidenced." And: "A green CI, ledger signature, or Merkle proof does **not** raise physics claim level." And: "Software readiness (tests, CI) is tracked separately from claim level."
- `docs/LIFECYCLE.md` Promote to ACTIVE: "Reference to ADL-Governance" and "SECURITY.md present."

`README.md` states the purpose. `SECURITY.md` is present. Tests and `.github/workflows/python-tests.yml` exist. Green CI is an Actions conclusion, not VSA completeness and not claim Level 5.

## Claim tag

| Subject | Tag |
|---------|-----|
| Software tests / CI | Separate from claim level. Not Level 5. |
| VSA completeness | **UNVERIFIED** beyond unit tests (registry). |
| Cognitive performance, mind, consciousness, sentience, general intelligence | **Not established.** Not tagged above Level 1. Measured cells, if any, stay in `results/execution_record.json` and `docs/AUDIT_SEEM_COMPLETION.md`. |
| Physics, residual force, Ware, thrust, energy extraction | Hypothesis-grade, offline only. Not Level 4 or 5. |

## Floors left unchanged

- `network_access=false` remains false. `core/network_guard.py` refuses a connection before any socket call.
- Invertibility floor remains **0.92** (`CleanRoomVSA.DEFAULT_MIN_INVERTIBILITY` and `manifests/CONSTITUTION_v1.3.md`).
- This note does not edit `manifests/CONSTITUTION_v1.3.md`.

No RealityOS, Sunder, or second clean-room engine is claimed from this document.
