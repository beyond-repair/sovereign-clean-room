# CleanRoomGodotBridge Protocol (Project Cold Boot)

## Transport

- **Unix domain socket only** (path under workspace, default `workspace/ipc/cold_boot.sock`)
- **No TCP / UDP / external hosts**
- Framing: **NDJSON** (one JSON object per line, UTF-8)

`network_access: false` is mandatory. Do not open network sockets from the Godot or C++ side for this bridge.

## Request

```json
{"id": "client-1", "op": "ping"}
```

## Response

```json
{"id": "client-1", "ok": true, "pong": true, "dim": 8192, "network_access": false, "transport": "unix_socket"}
```

## Operations

| op | Purpose |
|----|---------|
| `ping` | Liveness + dim |
| `telemetry` | Engine / ledger / memory snapshot |
| `memory_recall` | `{query, top_k?}` → hits (≥ τ 0.92) |
| `memory_remember` | `{content, meta?}` → episode_id + ledger |
| `shacl_check` | `{data, shape_id?}` constitutional / mapping |
| `skill_run` | `{package, payload?}` Gate + Ed25519 + SHACL |
| `ledger_append` | `{event_type?, payload?}` append-only chain |
| `ledger_verify` | Hash-chain continuity |
| `vsa_similarity` | `{a, b}` codebook atom cosine/phase sim |

## Godot 4.x / C++ notes

1. Connect with `socket(AF_UNIX, SOCK_STREAM, 0)` to the sock path.
2. Send one JSON line; read one JSON line.
3. Prefer GDExtension or a thin C++ helper; GDScript can use a local helper process if needed.
4. Never pass skill packages that set `network_access: true` — Gate rejects them.

## Security

- Socket path must remain under the sovereign workspace directory.
- Skill execution requires valid Ed25519 signatures when `require_skill_signature=true`.
- Game telemetry is recorded with `source=godot` / `godot_cold_boot` on the audit ledger.
