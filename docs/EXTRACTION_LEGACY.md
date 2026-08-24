# EXTRACTION_LEGACY — Stage-1 Pattern Provenance

**Governance:** ADL-Governance · **Date opened:** 2026-08-24  
**Target substrate:** `sovereign-clean-room`

All extractions are **pattern-only** rewrites. No whole files copied.  
No OpenAI / Anthropic / local-LLM / HTTP / GitHub API runtime code retained.

**Verification (2026-08-24):** `python -m pytest tests/test_stage1_extraction.py -q` → **10 passed**.

---

## Log

| Date | Source | Target | Pattern | Status |
|------|--------|--------|---------|--------|
| 2026-08-24 | beyond-repair/My-mind-A.I. / task_class.py | core/episodic_memory.py → TaskAtom | Immutable task event (title, description, complexity → payload) | VERIFIED |
| 2026-08-24 | beyond-repair/My-mind-A.I. / taskqueue_class.py | core/episodic_memory.py → EpisodicMemoryLedger | Ordered task queue → append-only atom chain | VERIFIED |
| 2026-08-24 | beyond-repair/My-mind-A.I. / delegate_class.py | core/episodic_memory.py → event_type=assigned | Agent assignment as atom, not mutable agent state | VERIFIED |
| 2026-08-24 | beyond-repair/My-mind-A.I. / orchestrate_agent_tasks.py | core/episodic_memory.py + memskill | Orchestration → Episode reconstruction | VERIFIED |
| 2026-08-24 | beyond-repair/My-mind-A.I. / gpt_agent.py, main.py | core/memskill.py → promote_memskill() | Completed work → permanent skill (LLM stripped) | VERIFIED |
| 2026-08-24 | beyond-repair/Gia---General-Intelligence-Assistant / base_agent.py | core/capability_registry.py → CapabilityDescriptor | Capability declaration interface | VERIFIED |
| 2026-08-24 | beyond-repair/Gia---General-Intelligence-Assistant / workflow.py, workflow_engine.py, task_processor.py | core/capability_registry.py → SkillManifest | Workflow metadata / registration (network code discarded) | VERIFIED |
| 2026-08-24 | beyond-repair/Gia agent implementations | core/capability_registry.py | Tool registration pattern only | VERIFIED |
| 2026-08-24 | beyond-repair/Auto_Legion | core/episodic_memory.py → TaskAtom transition events | Atomic work unit / hand-off concept | VERIFIED |
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

Source repos whose rows are **VERIFIED** may receive `ARCHIVED.md` and `gh repo archive`.

**Full-suite gate (separate):** `python -m pytest tests/ -q` currently fails collection on missing `core/_vsa_part_1.py` … `_vsa_part_N.py` (incomplete VSA restore from prior workstream). Stage-1 extraction modules do not depend on the assembled VSA engine. Archive of *legacy extraction sources* is allowed once VERIFIED; archive of SEEM supersession targets should wait until full CI is green again.
