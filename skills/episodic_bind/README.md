# Skill: `episodic_bind` v1.0.0

**First gated skill package** for SEEM Clean-Room v1.3.1.

## Sovereignty

| Control | Value |
|---------|-------|
| `network_access` | **false** |
| `file_system_access` | none |
| `execution_mode` | sandboxed_python |

## Behavior

1. Requires Jump-Start primitives (`SELF` … `FAILURE`).
2. Maps a local `note` string → deterministic FHRR filler (SHA-256 seed).
3. Binds `EPISODIC ⊙ filler`, unbinds, scores invertibility.
4. If score ≥ 0.92 → touch `SUCCESS` (optional register `episodic_note_*`).
5. Else → touch `FAILURE` and return FAIL.

## Run

```python
from clean_room_vsa import CleanRoomVSAEngine, CleanRoomGate
from skills.episodic_bind.skill import run_via_gate

vsa = CleanRoomVSAEngine()
vsa.jump_start_v01()
gate = CleanRoomGate(vsa)
print(run_via_gate(gate, note="first local memory"))
```

Or:

```bash
python tests/test_skill_episodic_bind.py
```

## Signature

`UNSIGNED_DEV_PLACEHOLDER` — development only. Production packages must carry a real Ed25519 signature over package bytes.
