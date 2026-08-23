<div align="center">

# SEEM

### Sovereign Clean-Room · Final Form

**Offline cognitive substrate** — FHRR · BaNEL · gated skills · atomic persistence

[![Status](https://img.shields.io/badge/status-ACTIVE-22c55e?style=for-the-badge)](https://github.com/beyond-repair/sovereign-clean-room)
[![Core](https://img.shields.io/badge/core-v1.3.x-0ea5e9?style=for-the-badge)](manifests/CONSTITUTION_v1.3.md)
[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](requirements.txt)
[![Governance](https://img.shields.io/badge/ADL--Governance-7c3aed?style=for-the-badge)](https://github.com/beyond-repair/ADL-Governance)
[![CI](https://img.shields.io/github/actions/workflow/status/beyond-repair/sovereign-clean-room/python-tests.yml?style=for-the-badge&label=CI)](https://github.com/beyond-repair/sovereign-clean-room/actions)

**Canonical home for SEEM** · supersedes all prior SEEM forks

</div>

---

## Why this exists

Most agent stacks lean on cloud APIs and opaque weights. **SEEM** is the opposite bet: a **small, pure-NumPy** vector-symbolic core with a hard **Clean-Room** boundary — untrusted work stays outside the symbolic engine, failures become **BaNEL** evidence, and state is **atomically** persisted.

| Layer | What you get |
|-------|----------------|
| **Core** | FHRR engine · resonator · invertibility gate · Jump-Start primitives |
| **Boundary** | Ed25519 skill packages · SHACL subset · `network_access: false` |
| **Runtime** | Orchestrator · daemon · ledger · episodic memory · CLI |
| **Defense** | JKillnHide integrity watchdog |
| **Physics bridge** | Hypothesis-grade only — claim level ≤ 2 |

---

## Quick start

```bash
git clone https://github.com/beyond-repair/sovereign-clean-room.git
cd sovereign-clean-room
pip install -r requirements.txt

python core/clean_room_cli.py init -w ./sovereign_workspace
python core/clean_room_cli.py status -w ./sovereign_workspace
python tests/test_canonical_v13.py
```

---

## Architecture (at a glance)

```text
        ┌──────────────────────────────────────┐
        │         Clean-Room Gate              │
        │   signature · SHACL · sandbox        │
        └──────────────┬───────────────────────┘
                       │
        ┌──────────────▼───────────────────────┐
        │     FHRR Core (dim = 8192)           │
        │  bind · unbind · BaNEL · Jump-Start  │
        └──────────────┬───────────────────────┘
                       │
     orchestrator · daemon · ledger · memory · CLI
```

**Design invariants**

1. Small but powerful — no heavy frameworks in core  
2. Clean-Room boundary — symbolic engine stays pure  
3. Personal uniqueness — MemSkills earned from history  
4. Controlled jump-start — sealed primitives, then local growth  
5. Geometric ≠ constitutive — scale ratios are not couplings  

---

## Documentation

| Doc | Purpose |
|-----|---------|
| [CONSTITUTION_v1.3](manifests/CONSTITUTION_v1.3.md) | Locked invariants |
| [BLOCK_SYSTEM](docs/BLOCK_SYSTEM.md) | Isolation theory |
| [MIGRATION_FROM_SEEM](docs/MIGRATION_FROM_SEEM.md) | From legacy SEEM |
| [LEGACY](docs/LEGACY.md) | Superseded repos |

---

## Scope

| In | Out |
|----|-----|
| Cognitive substrate, isolation, MemSkill/BaNEL | Validated propulsion / energy claims |
| Offline skills & audit trails | Cloud agent marketplaces |
| Hypothesis-grade physics *bridge* | Product Digital Double (separate repo) |

---

<div align="center">

**Part of [Atomic Dream Labs](https://github.com/beyond-repair)** · Governed by [ADL-Governance](https://github.com/beyond-repair/ADL-Governance)

<sub>Legacy SEEM-2.0 / Cognitive-Microservice / seem-block-system → superseded by this repository</sub>

</div>
