# Repository Grouping & Architecture Map (`beyond-repair`)

*As of August 21, 2026*

This document defines the structural boundaries across the `beyond-repair` GitHub account (~53 repositories). To avoid fragmentation, **all active SEEM engineering** is consolidated under the canonical core.

**Canonical substrate:** [`beyond-repair/sovereign-clean-room`](https://github.com/beyond-repair/sovereign-clean-room)

---

## Group A — SEEM / Clean-Room (Canonical Substrate)

| Repository | Role |
|------------|------|
| **`sovereign-clean-room`** | **Canonical / hot** — offline control plane |
| `SEEM-2.0-Self-Evolving-Emergent-Mind` | Legacy — origin blueprint |
| `SEEM-Cognitive-Microservice` | Legacy — superseded; points to clean-room |
| `SEEM-Cognitive_Microservice` | Legacy — near-duplicate |
| `seem-block-system` | Legacy — isolation theorem absorbed as reference |

### In-core modules (Group A implementation surface)

| Module | Function |
|--------|----------|
| `core/clean_room_vsa.py` | FHRR dim=8192, BaNEL, Jump-Start, Gate, prune |
| `core/skill_crypto.py` | Ed25519 offline skill signing |
| `core/clean_room_orchestrator.py` | Multi-skill signed pipelines |
| `core/clean_room_ledger.py` | Hash-chained audit + checkpoints |
| `core/clean_room_daemon.py` | Autonomous offline task cycles |
| `core/clean_room_memory.py` | Episodic FHRR memory store |
| `core/clean_room_shacl.py` | Offline SHACL-subset + neuro bridge |
| `core/clean_room_model.py` | Local LLM bridge (loopback only) |
| `core/clean_room_cli.py` | Unified workspace CLI |
| `core/clean_room_dashboard.py` | `127.0.0.1` telemetry UI |
| `core/clean_room_godot_bridge.py` | Unix-socket Cold Boot IPC |
| `core/clean_room_jkillnhide.py` | Workspace integrity watchdog |
| `core/clean_room_physics.py` | Ware/SPARC phenomenological bridge |

**Policy:** New SEEM features land **only** in `sovereign-clean-room`. Do not fork parallel “final form” cores.

---

## Group B — Ware / Coherence Drive / CFT–IQG (Theoretical Physics)

**Focus:** Mathematical modeling of alternative gravity / coherence frameworks and the Ware Constant \(W \approx 0.08\).

### Coherence Drive cluster

| Repo | Role |
|------|------|
| `coherence-drive` | Master integration claim |
| `-ware-constant-derivation` | \(W \approx 0.08\) derivation |
| `ware-constant-phenomenology` | Cross-scale phenomenology |
| `m2-renormalization-law` | \(W(n)\) exponential law |
| `stress-tensor-modification` | \(T_{\rm eff}\) Ware term |
| `momentum-closure` | Surface force / residual flux |
| `topological-pinch` | Aft-face bias narrative |
| `sierpinski-geometry-045` | 0.45 asymmetric geometry |
| `thrust-target-30` | \(3\times10^{-8}\) N/W anchor |

### CFT / IQG / related theory

| Repo | Role |
|------|------|
| `CFTv3.3-IQG-Unified-Framework` | Unified CFT + IQG |
| `CFT-v3.1` | Screened metric white paper |
| `CFT-v3.0` | Archived / private ancestor |
| `-text-informational-fork-protocol-` | Informational locality protocol |
| `-Entanglement-and-Emergence` | Emergent gravity notes |
| `The-Origin-Point-Hypothesis.` | Foundational TeX |

**Status:** *Hypothesis-grade.*

- Clean-room physics bridge treats SPARC-style fits as **phenomenological**.
- Symbolic pathway `δu_vac → T_eff → ΔF` is defined; **`δu_vac → P_out` is not**.
- `χ_vac` and `𝒢` remain unresolved constitutive parameters.
- Energy extraction and experimental thrust remain **mathematically / empirically open**.

**Policy:** Theory stays in Group B. Clean-room may *bridge* metrics into FHRR/ledger; it does **not** absorb Drive claims as proven fact.

---

## Group C — Products & Agent Lines

**Focus:** Autonomous assistants and virtual workforce engines.

| Repo | Notes |
|------|-------|
| `Gia---General-Intelligence-Assistant` | Autonomous assistant product |
| `Digital_Double_virtual_workforce` | Public workforce line |
| `Digital_Double_Virtual_Workforce_4.2` / `4.` | Private variants |
| `DigitalDoubleVirtualWorkforce3.5` | CAP / fault tolerance |
| `digital-double-mobile` / `Digital-Double_Mobile` | Mobile |
| `AtomicNexusAI`, `Auto_Legion`, `Agent-Snake`, … | Earlier experiments |

**Policy:** Separate product experiments. **Do not** merge into `sovereign-clean-room` without architectural review and a gated skill boundary.

---

## Group D — Security & Integrity

| Asset | Role |
|-------|------|
| `AEGIS-Project-Nehemiah-` | Host integrity graph / baseline / restore |
| `VigilE.S.A.-Enhanced-Security` | Broader security platform (satellite) |
| `optimization-limit-conjecture` | Graph obstruction floors |
| **JKillnHide** (in clean-room) | **In-core** workspace file integrity + fail-closed daemon policy |

**Policy:** Clean-room defense is **workspace-local** only—not a substitute for full host security products.

---

## Group E — Trading & Crypto Experiments

Examples: `FortiTrade_Multi-Strategy`, Fantom bots, `btc-trading`, `BlockSwarm`, `automate_passive_income`.

**Status:** Satellite utilities; **isolated** from Clean-Room runtime and SEEM identity state.

---

## Group F — Tools & Dormant Stubs

Examples: `RepoRover-`, `-Py2APK-main`, `Quantumclustering`, `DevelopTool-Unified-Dev-Environment`, `smart_home_BCI`, profile `beyond-repair`, misc stubs.

**Status:** Periodically audited for **GitHub archive**. No dependency from Group A.

---

## Hard boundaries (locked)

1. **Group A is the only active SEEM engineering line.**
2. **Group B is theory** until parameter closure + independent experimental verification.
3. **Group C products** do not share process memory or trust roots with Group A unless mediated by signed offline skills.
4. **Clean-Room networking:** `network_access: false` (loopback / Unix socket only where applicable).
5. **Skill execution:** Ed25519 + SHACL + Gate; unsigned packages fail closed by default.

### Dependency sketch

```
SEEM core (A)  ←── gated skills only ──┐
                                       │
        optional: Ware numerics (B) ───┤  after constitutive closure
        optional: AEGIS hooks (D) ─────┤
        never: trading bots as core ───┘

CFT theory ──related──► Ware phenomenology (B)
Digital Double / Gia (C) ──product──► separate from SEEM constitution
```

---

## Hygiene checklist

1. Archive or mark dormant Group F repos when inactive.
2. Banner Group B READMEs: *hypothesis-grade / not experimentally closed* where missing.
3. Keep Digital Double / Gia READMEs explicit: *not* the SEEM constitutional substrate.
4. After trusted `clean_room_cli init`, run JKillnHide `write_baseline()` before production daemon cycles.

---

*Document owner: beyond-repair / Atomic Dream Labs — structural map only; not a physics endorsement.*
