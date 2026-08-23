<div align="center">

# 🧠 SEEM

## The cognitive runtime that **doesn't need the cloud**

### Sovereign Clean-Room · Final Form

[![ACTIVE](https://img.shields.io/badge/●_ACTIVE-22c55e?style=for-the-badge)](https://github.com/beyond-repair/sovereign-clean-room)
[![v1.3](https://img.shields.io/badge/Core-v1.3-0ea5e9?style=for-the-badge)](manifests/CONSTITUTION_v1.3.md)
[![CI](https://img.shields.io/github/actions/workflow/status/beyond-repair/sovereign-clean-room/python-tests.yml?style=for-the-badge)](https://github.com/beyond-repair/sovereign-clean-room/actions)
[![Python](https://img.shields.io/badge/Pure_NumPy-core-3776AB?style=for-the-badge&logo=python&logoColor=white)](requirements.txt)

**Stop renting intelligence. Run a substrate you can open, gate, and keep.**

</div>

---

## The problem

Your “AI stack” is a thin wrapper over someone else's model, someone else's policy, someone else's outage.

**SEEM** is built for the opposite bet:

- **Offline-first** — `network_access: false` is a hard rule, not a slide  
- **Small core** — pure NumPy FHRR, not a 40GB mystery blob  
- **Clean-Room** — untrusted skills don't contaminate the symbolic engine  
- **Memory that means something** — Jump-Start atoms, episodic store, crash-safe twin state  
- **Failures that teach** — BaNEL turns errors into directional signal  

---

## What you get

| Layer | Punchline |
|-------|-----------|
| **FHRR core** | Bind · unbind · bundle · gate at τ = 0.92 |
| **Clean-Room Gate** | Ed25519 packages · SHACL · sandbox |
| **Orchestrator / Daemon** | Multi-skill pipelines · resume after crash |
| **Ledger** | Append-only · hash-chained · offline |
| **JKillnHide** | Workspace integrity — drift freezes execution |
| **CLI** | `init` · `run` · `status` · `physics` · `jkillnhide` |

```text
   Untrusted skill ──► Gate ──► Core ──► Ledger / Memory
                         ▲
                    signature + SHACL
                    network_access = false
```

---

## 60-second start

```bash
git clone https://github.com/beyond-repair/sovereign-clean-room.git
cd sovereign-clean-room && pip install -r requirements.txt

python core/clean_room_cli.py init -w ./sovereign_workspace
python core/clean_room_cli.py status -w ./sovereign_workspace
python tests/test_canonical_v13.py
```

---

## This is the final form

All prior SEEM repos are **history**. This is the only active substrate.

| Legacy | Status |
|--------|--------|
| SEEM-2.0 · Cognitive-Microservice · seem-block-system | **SUPERSEDED → here** |

**Not sold as:** AGI in a box · validated vacuum propulsion · “just trust the dream phase.”  
**Sold as:** a serious offline control plane you can run, test, and extend.

---

<div align="center">

### ⭐ If sovereignty isn't a slogan for you — star it. Clone it. Stress it.

[**Atomic Dream Labs**](https://github.com/beyond-repair) · [Governance](https://github.com/beyond-repair/ADL-Governance)

</div>
