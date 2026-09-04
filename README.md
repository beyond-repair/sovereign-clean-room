<div align="center">

```
╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║   ██████╗ ██████╗ ███╗   ███╗██████╗ ██╗██╗     ███████╗██████╗  ║
║  ██╔════╝██╔═══██╗████╗ ████║██╔══██╗██║██║     ██╔════╝██╔══██╗ ║
║  ██║     ██║   ██║██╔████╔██║██████╔╝██║██║     █████╗  ██████╔╝ ║
║  ██║     ██║   ██║██║╚██╔╝██║██╔═══╝ ██║██║     ██╔══╝  ██╔══██╗ ║
║  ╚██████╗╚██████╔╝██║ ╚═╝ ██║██║     ██║███████╗███████╗██║  ██║ ║
║   ╚═════╝ ╚═════╝ ╚═╝     ╚═╝╚═╝     ╚═╝╚══════╝╚══════╝╚═╝  ╚═╝ ║
║                                                                  ║
║              ＨＥＩＧＨＴＳ  ·  ＤＩＳＴＲＩＣＴ  ０３               ║
╚══════════════════════════════════════════════════════════════════╝
```

# SOVEREIGN CLEAN-ROOM

### Offline cognitive substrate — the runtime you **own**

**THE CITY WRITES ITS OWN REALITY.**  
**YOU JUST EDIT IT.**

[![ACTIVE](https://img.shields.io/badge/●_ACTIVE-a855f7?style=for-the-badge&labelColor=0f0f23)](https://github.com/beyond-repair/sovereign-clean-room)
[![v1.3 FHRR](https://img.shields.io/badge/Core-v1.3_Hyperspherical-22d3ee?style=for-the-badge&labelColor=0f0f23)](manifests/CONSTITUTION_v1.3.md)
[![CI](https://img.shields.io/github/actions/workflow/status/beyond-repair/sovereign-clean-room/python-tests.yml?style=for-the-badge&labelColor=0f0f23)](https://github.com/beyond-repair/sovereign-clean-room/actions)
[![Offline](https://img.shields.io/badge/network__access-FALSE-ef4444?style=for-the-badge&labelColor=0f0f23)](#)

```
STABILITY  ████████████████████░░░░  78%
ALERT      ░░░░░░░░░░░░░░░░░░░░░░░░  12%
```

</div>

---

## ▌ MAIN OBJECTIVE

**REACH THE CORE TOWER** — Bypass the security grid.  
Run a fully offline FHRR cognitive twin with cryptographic skill gates, append-only memory, and fail-closed integrity.

| Status | Item |
|:------:|------|
| ☑ | Path A static engine live |
| ☑ | CleanRoomGate + Ed25519 + SHACL |
| ☑ | Jump-Start v0.1 pinned atoms |
| ☑ | BaNEL failure ledger |
| ☑ | CI green on main |

---

## ▌ WHY THIS SURFACE EXISTS

| Typical stack | Clean-Room |
|---------------|------------|
| Cloud model + thin wrapper | **Local pure-NumPy FHRR core** |
| Skills run with full privileges | **Ed25519 + SHACL gate before touch** |
| Failures discarded | **BaNEL phase repulsion** |
| Opaque memory | **Jump-Start atoms + hash ledger** |
| “Offline” optional | **`network_access: false` enforced** |

**Canonical SEEM home.** All prior SEEM forks are superseded.

---

## ▌ VISUAL WORKFLOW — VERSION FORK

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

### Step-by-step

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

## ▌ TOOLS

| # | Tool | Function |
|:-:|------|----------|
| 1 | **SCAN** | Inspect workspace integrity + codebook stats |
| 2 | **FORK** | Create parallel twin states (version fork) |
| 3 | **SPIKE** | Inject skill under gate (Ed25519 + SHACL) |
| 4 | **ANCHOR** | Pin Jump-Start atoms / ledger checkpoint |
| 5 | **ESCAPE** | Freeze on drift (JKillnHide defense) |

---

## ▌ HOW IT FITS THE LAB

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
  coherence-drive = RESEARCH only
```

---

## ▌ QUICK START

```bash
git clone https://github.com/beyond-repair/sovereign-clean-room.git
cd sovereign-clean-room && pip install -r requirements.txt
python core/clean_room_cli.py init -w ./sovereign_workspace
python core/clean_room_cli.py status -w ./sovereign_workspace
python -m pytest tests/ -q
```

---

<div align="center">

```
YOU WERE HERE BEFORE.
VERSION 17 FAILED.
DO NOT TRUST SABLE.
THE CITY REMEMBERS.
```

**REWRITE · BUILD · TRANSCEND**

[Atomic Dream Labs](https://github.com/beyond-repair) · [ADL-Governance](https://github.com/beyond-repair/ADL-Governance)

</div>
