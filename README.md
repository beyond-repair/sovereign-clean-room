<div align="center">

# 🧠 SEEM · Sovereign Clean-Room

### Offline cognitive substrate — the runtime you **own**

[![ACTIVE](https://img.shields.io/badge/●_ACTIVE-22c55e?style=for-the-badge)](https://github.com/beyond-repair/sovereign-clean-room)
[![v1.3](https://img.shields.io/badge/Core-v1.3-0ea5e9?style=for-the-badge)](manifests/CONSTITUTION_v1.3.md)
[![CI](https://img.shields.io/github/actions/workflow/status/beyond-repair/sovereign-clean-room/python-tests.yml?style=for-the-badge)](https://github.com/beyond-repair/sovereign-clean-room/actions)

</div>

---

## Why it is unique

| Typical stack | Clean-Room |
|---------------|------------|
| Cloud model + thin wrapper | **Local pure-NumPy FHRR core** |
| Skills run with full privileges | **Ed25519 + SHACL gate before touch** |
| Failures discarded | **BaNEL phase repulsion** |
| Opaque memory | **Jump-Start atoms + hash ledger** |
| “Offline” optional | **`network_access: false` enforced** |

**Canonical SEEM home.** All prior SEEM forks are superseded.

---

## Visual workflow

```text
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ 1. WORKSPACE │───►│ 2. GATE      │───►│ 3. FHRR CORE │───►│ 4. MEMORY    │
│ init / load  │    │ sign·SHACL   │    │ bind·unbind  │    │ episodic     │
│ twin state   │    │ sandbox      │    │ BaNEL·τ=0.92 │    │ + ledger     │
└──────────────┘    └──────────────┘    └──────────────┘    └──────┬───────┘
                                                                   │
┌──────────────┐    ┌──────────────┐    ┌──────────────┐           │
│ 7. DEFENSE   │◄───│ 6. DAEMON    │◄───│ 5. ORCHESTR. │◄──────────┘
│ JKillnHide   │    │ resume loop  │    │ skill chain  │
│ freeze on    │    │ checkpoints  │    │ telemetry    │
│ drift        │    │              │    │              │
└──────────────┘    └──────────────┘    └──────────────┘
```

### Step-by-step — how & why

| Step | What happens | Why |
|-----:|--------------|-----|
| **1** | `cli init` creates workspace, loads Jump-Start primitives | Deterministic birth — not empty black box |
| **2** | Skill packages verified (Ed25519) + SHACL shapes | Untrusted code never touches core raw |
| **3** | FHRR bind/unbind, sparse cleanup, invertibility gate | Compositional memory without a 40GB weight dump |
| **4** | Episodic store + append-only hash-chained ledger | Recall + audit without a remote DB |
| **5** | Orchestrator runs multi-skill pipelines offline | Continuity across tasks, same core state |
| **6** | Daemon resumes from last valid checkpoint | Crash ≠ amnesia |
| **7** | JKillnHide compares workspace integrity | Drift can freeze execution before poison spreads |

---

## How it works with the rest of the lab

```text
                    ADL-Governance (rules & claim levels)
                              │
         ┌────────────────────┼────────────────────┐
         ▼                    ▼                    ▼
  sovereign-clean-room   BlockSwarm          forge-aegis
  (offline brain)        (on-chain advice≠  (integrity
         │                execute)            contract)
         │                    │                    │
         └──────── one-way attestation ────────────┘
                          optional

  Digital Double = product agents (separate surface)
  coherence-drive = RESEARCH only (physics bridge may run
                    offline here — does NOT raise claim level)
```

---

## Quick start

```bash
git clone https://github.com/beyond-repair/sovereign-clean-room.git
cd sovereign-clean-room && pip install -r requirements.txt
python core/clean_room_cli.py init -w ./sovereign_workspace
python core/clean_room_cli.py status -w ./sovereign_workspace
python tests/test_canonical_v13.py
```

---

<div align="center">

[Atomic Dream Labs](https://github.com/beyond-repair) · [ADL-Governance](https://github.com/beyond-repair/ADL-Governance)

</div>
