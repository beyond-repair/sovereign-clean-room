# SEEM — Sovereign Clean-Room Final Form

**Canonical repository for SEEM (Sovereign Evolving Emergent Mind)**  
**Core version:** 1.3.1 · **Status:** ACTIVE · **Maturity:** 4  
**Governance:** [ADL-Governance](https://github.com/beyond-repair/ADL-Governance)

This is the single active home for the SEEM cognitive substrate.

## What lives here

| Layer | Content |
|-------|---------|
| **Core** | Pure-NumPy FHRR engine, resonator, BaNEL, invertibility gate, atomic persistence, Clean-Room sandbox |
| **Constitution** | Locked invariants (`manifests/CONSTITUTION_v1.3.md`) |
| **Isolation theory** | Block-system isolation (`docs/BLOCK_SYSTEM.md`) |
| **Legacy map** | Superseded SEEM repos (`docs/LEGACY.md`) |
| **Skills / schema** | `skills/`, `schemas/skill_package_v1.json` |
| **Physics bridge** | Hypothesis-grade only (`core/clean_room_physics.py`) — claim level ≤2 |

## Design invariants

1. **Small but powerful** — no heavy frameworks in the core  
2. **Clean-Room boundary** — untrusted work outside the symbolic engine  
3. **Personal uniqueness** — earned MemSkills from history  
4. **Controlled jump-start** — sealed then local  
5. **Geometric ≠ constitutive** — scale ratios vs couplings  

## Quick start

```bash
git clone https://github.com/beyond-repair/sovereign-clean-room.git
cd sovereign-clean-room
pip install -r requirements.txt
python core/clean_room_vsa.py
python tests/test_canonical_v13.py
```

## Scope boundary

- **In scope:** cognitive substrate, Clean-Room isolation, MemSkill/BaNEL, persistence  
- **Out of scope:** validated Ware propulsion, product Digital Double, trading bots  

See [REPO_GROUPS.md](docs/REPO_GROUPS.md) and [ADL-Governance registry](https://github.com/beyond-repair/ADL-Governance/blob/main/docs/repository_registry.md).

## Superseded SEEM repositories

| Legacy repo | Disposition |
|-------------|-------------|
| SEEM-2.0-Self-Evolving-Emergent-Mind | SUPERSEDED |
| SEEM-Cognitive-Microservice | SUPERSEDED |
| SEEM-Cognitive_Microservice | SUPERSEDED |
| seem-block-system | Absorbed → `docs/BLOCK_SYSTEM.md` |

**This repository is the final form for SEEM.**
