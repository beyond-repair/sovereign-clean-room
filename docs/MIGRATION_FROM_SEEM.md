# Migration from legacy SEEM → sovereign-clean-room

**Successor (canonical):** this repository  
**Superseded:** SEEM-2.0-Self-Evolving-Emergent-Mind, SEEM-Cognitive-Microservice, SEEM-Cognitive_Microservice, seem-block-system

## What moves

| Legacy idea | Clean-Room location |
|-------------|---------------------|
| Resonator VSA / FHRR | `core/clean_room_vsa.py` |
| BaNEL | `BaNELController` in VSA engine |
| Invertibility gate | `min_invertibility=0.92` |
| Atomic persistence | `save` / `load` twin state |
| Block isolation | `docs/BLOCK_SYSTEM.md` |
| Skills / MemSkills | `skills/`, signed packages |

## What does not move

- Telegram / cloud bridges (optional later; offline-first)
- Claims that Dream Phase is fully production-complete without tests
- Any Ware physics as “validated propulsion”

## Quick start

```bash
git clone https://github.com/beyond-repair/sovereign-clean-room.git
cd sovereign-clean-room
pip install -r requirements.txt
python core/clean_room_cli.py init -w ./sovereign_workspace
python core/clean_room_cli.py status -w ./sovereign_workspace
python tests/test_canonical_v13.py
```

## Attestation export (offline)

```bash
python core/clean_room_cli.py physics eval -w ./sovereign_workspace
python scripts/export_attestation.py --from-physics-json result.json -o attestation.json
```

See `core/clean_room_attestation.py`.

## Governance

[ADL-Governance](https://github.com/beyond-repair/ADL-Governance)
