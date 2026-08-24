# EXTRACTION_LEGACY — Stage-1 Pattern Provenance

**Governance:** ADL-Governance · **Date opened:** 2026-08-24  
**Target substrate:** `sovereign-clean-room`

All extractions are **pattern-only** rewrites. No whole files copied.  
No OpenAI / Anthropic / local-LLM / HTTP / GitHub API runtime code retained.

---

## Log

| Date | Source | Target | Pattern | Status |
|------|--------|--------|---------|--------|
| 2026-08-24 | beyond-repair/My-mind-A.I. / task_class.py | core/episodic_memory.py → TaskAtom | Immutable task event (title, description, complexity → payload) | EXTRACTED |
| 2026-08-24 | beyond-repair/My-mind-A.I. / taskqueue_class.py | core/episodic_memory.py → EpisodicMemoryLedger | Ordered task queue → append-only atom chain | EXTRACTED |
| 2026-08-24 | beyond-repair/My-mind-A.I. / delegate_class.py | core/episodic_memory.py → event_type=assigned | Agent assignment as atom, not mutable agent state | EXTRACTED |
| 2026-08-24 | beyond-repair/My-mind-A.I. / orchestrate_agent_tasks.py | core/episodic_memory.py + memskill | Orchestration → Episode reconstruction | EXTRACTED |
| 2026-08-24 | beyond-repair/My-mind-A.I. / gpt_agent.py, main.py | core/memskill.py → promote_memskill() | Completed work → permanent skill (LLM stripped) | EXTRACTED |
| 2026-08-24 | beyond-repair/Gia---General-Intelligence-Assistant / base_agent.py | core/capability_registry.py → CapabilityDescriptor | Capability declaration interface | EXTRACTED |
| 2026-08-24 | beyond-repair/Gia---General-Intelligence-Assistant / workflow.py, workflow_engine.py, task_processor.py | core/capability_registry.py → SkillManifest | Workflow metadata / registration (network code discarded) | EXTRACTED |
| 2026-08-24 | beyond-repair/Gia agent implementations | core/capability_registry.py | Tool registration pattern only | EXTRACTED |
| 2026-08-24 | beyond-repair/Auto_Legion | core/episodic_memory.py → TaskAtom transition events | Atomic work unit / hand-off concept | EXTRACTED |
| 2026-08-24 | beyond-repair/Agent-Snake | skills/templates/ (reference only) | Code-generation abstraction (no runtime) | PLANNED |

---

## Status legend

- **PLANNED** — mapped, not yet coded
- **EXTRACTED** — code landed in clean-room
- **VERIFIED** — tests green + hash/integrity checks pass
- **ARCHIVED** — source repo GitHub-archived after VERIFIED

---

## Integration notes

- Existing `clean_room_memory.py` (FHRR EpisodicMemoryStore) remains the vector recall layer.
- New `episodic_memory.py` (TaskAtom ledger) is the **symbolic / audit** layer that can feed content into FHRR via `Episode.content_summary()`.
- Existing `clean_room_ledger.py` may dual-write from `EpisodicMemoryLedger` for pipeline audit continuity.
- Existing `skill_crypto.py` signs MemSkill packages (Ed25519).
- `network_access: false` is forced at CapabilityRegistry and MemSkill boundaries.

---

## Archive gate

No source repository may move to ARCHIVED until its rows above are **VERIFIED** and this document is committed on `main`.
