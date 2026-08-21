# Skill signing keys (local)

```bash
python scripts/gen_skill_signing_key.py --out-dir keys --name skill_root
python scripts/sign_skill_package.py skills/episodic_bind/package.json \
  --signing-key keys/skill_root.sk --in-place
```

| File | Commit? |
|------|---------|
| `*.pub` | Optional (public trust root) |
| `*.sk` | **Never** |

Gate verification loads only verify keys you configure locally — no network fetch.
