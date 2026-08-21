# Gated skills

Skill packages admitted through the Clean-Room boundary live here.

Nothing in this directory executes inside the VSA core without:

1. Structured inputs  
2. Sanitized outputs  
3. BaNEL success/failure signals  
4. Optional distillation into MemSkills  

Schema: [`schemas/skill_package_v1.json`](../schemas/skill_package_v1.json)  
Core: `core/clean_room_vsa.py`

## Packages

| skill_id | Version | network_access | Description |
|----------|---------|----------------|-------------|
| `episodic_bind` | 1.0.0 | **false** | Bind local note to `EPISODIC` role; gate on invertibility ≥ 0.92 |

See `skills/episodic_bind/`.
