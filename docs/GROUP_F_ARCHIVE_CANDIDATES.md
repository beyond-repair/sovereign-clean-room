# Group F — Archive Target List

*Prepared 2026-08-21 — ops hygiene for `beyond-repair`*

Archiving makes a repository **read-only**, removes it from default “active” clutter, and **preserves full history**. It does not delete code.

Confirm each item still has no dependents before archiving.

---

## Primary archive candidates (Group F / dormant tools)

| Repository | Rationale |
|------------|-----------|
| `RepoRover-` | Dormant GitHub utility |
| `DevelopTool-Unified-Dev-Environment` | Old unified-dev stub |
| `-Py2APK-main` | One-off experiment |
| `optimization-limit-conjecture` | Unmerged theoretical stub (optional — keep if still researching) |
| `quantum_A.I._optimization.py` | Early quantum/AI experiment |
| `Quantumclustering` | Minimal / dormant |
| `smart_home_BCI` | One-off integration sketch |
| `Agent-Snake` | Early ML toy |
| `Auto_Legion` | Dormant agent experiment |
| `genieGPT` | Stub |
| `Code_Generation_AI_Program` | Stub |
| `My-mind-A.I.` / `new-program-1.01` | Very early mind experiments |
| `potential-garbanzo` | Private early agent stub |
| `test` | Private empty test repo |
| `automate_passive_income` | Dormant utility |

**Do not archive (wrong group):** anything in Group A (including legacy SEEM pointers until you choose to), Group B physics theory you still cite, active Digital Double, Gia, AEGIS, or trading bots you still run.

---

## Legacy SEEM (banner only — archive optional later)

These already carry **⚠️ SUPERSEDED** banners. Archiving is optional after a cooling period:

- `SEEM-2.0-Self-Evolving-Emergent-Mind`
- `SEEM-Cognitive-Microservice`
- `SEEM-Cognitive_Microservice`
- `seem-block-system`

---

## Batch archive via GitHub CLI

Requires `gh` authenticated as an account with admin on each repo.

```bash
# Review first
for r in \
  RepoRover- \
  DevelopTool-Unified-Dev-Environment \
  -Py2APK-main \
  quantum_A.I._optimization.py \
  Quantumclustering \
  smart_home_BCI \
  Agent-Snake \
  Auto_Legion \
  genieGPT \
  Code_Generation_AI_Program \
  "My-mind-A.I." \
  new-program-1.01 \
  automate_passive_income
do
  echo "Would archive: beyond-repair/$r"
done

# Execute (uncomment when ready)
# for r in RepoRover- DevelopTool-Unified-Dev-Environment -Py2APK-main \
#   quantum_A.I._optimization.py Quantumclustering smart_home_BCI \
#   Agent-Snake Auto_Legion genieGPT Code_Generation_AI_Program \
#   "My-mind-A.I." new-program-1.01 automate_passive_income
# do
#   gh repo archive "beyond-repair/$r" --yes
# done
```

Or one-shot:

```bash
gh repo archive beyond-repair/RepoRover- --yes
gh repo archive beyond-repair/DevelopTool-Unified-Dev-Environment --yes
gh repo archive beyond-repair/-Py2APK-main --yes
# ...etc
```

UI path: **Settings → Danger Zone → Archive this repository**.

---

## After archiving

1. Re-run account sweep; update `docs/REPO_GROUPS.md` counts if desired.
2. Keep Group B READMEs un-archived unless you explicitly retire a theory line.
3. Canonical work remains: **sovereign-clean-room** only.
