# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.3.x (CONSTITUTION_v1.3) | Yes |
| < 1.3 | No |

## Reporting a Vulnerability

Do **not** open a public issue for security-sensitive reports.

Email or private channel to the repository owner (`beyond-repair`). Include:
- Affected component / path
- Reproduction steps (if safe)
- Impact assessment
- Suggested mitigation (optional)

## Design Invariants (non-negotiable)

1. **Offline core**: No network access in the clean-room substrate. Skills that require network must be gated and signed.
2. **Fail-closed gates**: Ed25519 signature verification + SHACL validation on skill packages. Invalid or unsigned packages are rejected.
3. **No untrusted code execution**: Core never executes arbitrary code from skills without sandbox boundary enforcement.
4. **Atomic persistence**: Sibling-directory swap only; no partial writes of critical state.
5. **Cryptographic skill boundary**: All skill packages must conform to `schemas/skill_package_v1.json` and be signed with the repository signing key workflow.

## Dependency Policy

- Pin critical crypto dependencies (PyNaCl ≥ 1.6.2).
- Prefer minimal surface: NumPy + PyNaCl in core; no heavy frameworks.
- CI runs on every push/PR to main.

## Known Non-Goals

- This repository does not provide production threat-model coverage for multi-tenant cloud deployment.
- Residual-force / Ware / propulsion physics are external and admitted only as gated skills; they are not part of the core security boundary.

## Historical Notes

PyNaCl was bumped 1.5.0 → 1.6.2 (2026-09-05) for GHSA-mrfv-m5wm-5w6w / CVE-2025-69277 (incomplete curve-point validation).
