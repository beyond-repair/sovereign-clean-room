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

### The runtime you **own**

**THE CITY WRITES ITS OWN REALITY.**  
**YOU JUST EDIT IT.**

[![ACTIVE](https://img.shields.io/badge/●_ACTIVE-a855f7?style=for-the-badge&labelColor=0f0f23)](https://github.com/beyond-repair/sovereign-clean-room)
[![v1.3](https://img.shields.io/badge/Core-v1.3-22d3ee?style=for-the-badge&labelColor=0f0f23)](manifests/CONSTITUTION_v1.3.md)
[![CI](https://img.shields.io/github/actions/workflow/status/beyond-repair/sovereign-clean-room/python-tests.yml?style=for-the-badge&labelColor=0f0f23)](https://github.com/beyond-repair/sovereign-clean-room/actions)
[![Offline](https://img.shields.io/badge/network__access-FALSE-ef4444?style=for-the-badge&labelColor=0f0f23)](#)
[![Gate](https://img.shields.io/badge/Ed25519_+_SHACL-a855f7?style=for-the-badge&labelColor=0f0f23)](#)

```
STABILITY  ████████████████████░░░░  78%
ALERT      ░░░░░░░░░░░░░░░░░░░░░░░░  12%
```

</div>

---

## ▌ MAIN OBJECTIVE

**REACH THE CORE TOWER**

Offline cognitive substrate. Cryptographic skill gates. Fail-closed integrity.

---

## ▌ TOOLS

| # | Tool | |
|:-:|:----:|:-|
| 1 | **SCAN** | Inspect |
| 2 | **FORK** | Parallel states |
| 3 | **SPIKE** | Inject under gate |
| 4 | **ANCHOR** | Pin checkpoint |
| 5 | **ESCAPE** | Freeze on drift |

---

## ▌ BENCH / GOVERNANCE UPDATE (2026-09-30)

Phase I (FHRR) and Phase III (BaNEL) protocol, plus the MemSkill SHACL/Z3/Ed25519 promotion contract:

- `docs/benchmarks/PHASE_I_III_VALIDATION_PROTOCOL_v1.0.md` (locked)
- `docs/benchmarks/PHASE_I_III_BENCHMARK_PROTOCOL.md` (superseded draft)
- `docs/benchmarks/MEMSKILL_GOVERNANCE_PIPELINE.md`
- `shapes/mem_skill_shape.ttl`
- `core/clean_room_z3.py`
- `core/memskill_governance_gate.py`

`core/clean_room_shacl.py` is unchanged. Z3 and pyshacl are optional (`requirements-governance.txt`).

The stability and alert bars above are decorative. They are not measurements.

Completion-pass notes, claim classes, and deviations: `docs/AUDIT_SEEM_COMPLETION.md`. A benchmark cell is a measured result only when `results/execution_record.json` says so. Empty or `not_run` cells are not results.

## ▌ PORTFOLIO GOVERNANCE

Classification **ACTIVE**. Parent constitution: [ADL-Governance](https://github.com/beyond-repair/ADL-Governance). Claim tag, and the unchanged `network_access=false` and 0.92 floor, are in [docs/GOVERNANCE.md](docs/GOVERNANCE.md). `manifests/CONSTITUTION_v1.3.md` is not amended here. Cognitive and physics claims are not Level 4–5.

## ▌ QUICK START

Python **3.11, 3.12, or 3.13**. Commands assume the repository root. There is no separate build step: this is a library-plus-CLI, not a packaged wheel. `numpy==1.26.4` is installed on 3.11 and 3.12 (the CI interpreter is 3.11). On 3.13, `requirements.txt` selects a NumPy 2.x wheel because 1.26.4 has no cp313 build. PyNaCl stays pinned at 1.6.2.

```bash
git clone https://github.com/beyond-repair/sovereign-clean-room.git
cd sovereign-clean-room
python3 -m pip install -r requirements.txt
python3 core/clean_room_cli.py init -w ./sovereign_workspace
python3 core/clean_room_cli.py status -w ./sovereign_workspace
python3 core/clean_room_cli.py memory "cedar quartz" --remember -w ./sovereign_workspace
python3 core/clean_room_cli.py memory "cedar quartz" -w ./sovereign_workspace
python3 core/clean_room_cli.py ledger verify -w ./sovereign_workspace
python3 -m pytest tests/ -q
```

`init` writes a local workspace and the Jump-Start v0.1 atoms (`SELF`, `ENVIRONMENT`, `EPISODIC`, `SEMANTIC`, `SUCCESS`, `FAILURE`) under `sovereign_workspace/twin_state`. `status` and `ledger verify` should exit 0. Memory recall prints nearest episodes; it does not claim understanding. Unsigned skill packages are rejected. Signing keys stay local (`keys/README.md`); do not commit `*.sk`.

Optional governance benches (SHACL Turtle gate and Z3) are not required for the commands above:

```bash
python3 -m pip install -r requirements-governance.txt
```

Without them, five tests skip (`z3` or `pyshacl` missing). With them, the same suite runs those tests. This substrate is not a mind, and the decorative stability bar is not a measurement. Partial benchmark cells live only in `results/execution_record.json` when that file says they were run.

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
