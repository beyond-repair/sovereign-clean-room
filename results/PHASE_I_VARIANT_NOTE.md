# Phase I variant note — codebook superposition does not clear k=3

This is not a locked-grid result and it is not a pass.

## What the protocol locks

`docs/benchmarks/PHASE_I_III_VALIDATION_PROTOCOL_v1.0.md` section 1 locks `M = 1000` and `T_max = 7`. It does not name the resonator's initial distribution. Random unit-phasor init is an implementation choice of `resonator()` (configuration hash), not a protocol constant. Section 1 also locks the component law, component-wise binding, and phasor projection. Section 2.1 locks cosine-sum `I`. The CI floors stay 0.92 and 0.95. `network_access` stays false.

Codebook size is not a legal lever. Raising `T_max` is not a legal lever. Vector L2 normalization is a different substrate and was not used. Oracle init (the true factors) is not a measurement of blind retrieval.

## Variant that was implemented

`resonator_codebook_superposition` in `core/fhrr_protocol.py`. `run_cell(..., variant="codebook_superposition")`.

Each factor starts as `phasor_project` of the sum of the codebook rows (one shared vector, not the true factors). The update is the same soft cleanup as the locked runner, `xhat <- pi(A A^H p)`, for all 7 passes. The locked runner is unchanged when `variant` is omitted: smoke trials at `d=32` still match config sha256 `bcf87c53eef84d8384944ba651e4ef9c36c28582996558ce6c252e3540dce387` and the same `I` values.

## Recorded run

Machine record: `results/phase_I_variant_codebook_superposition.json`.

Code under test: `resonator_codebook_superposition` from commit `7dc0d93a7925a97c1c637d2f02108f71dee12ee3`, plus a configuration-label change that does not affect the samples (the k=3 and k=2 means below matched a run recorded before that label change). Seeds: codebook `20260930`, trial `20261001`, bootstrap `20260930`, `B=10000`. `gamma=0`, `d=8192`, `M=1000`, `N_noise=1`, `T_max=7`.

| k | N | mean I | I 95% CI | accuracy | accuracy 95% CI | config sha256 | floors |
|---|---|---|---|---|---|---|---|
| 3 | 16 | 0.028044020649339984 | [0.02014492488057777, 0.0358279525882108] | 0.0 | [0.0, 0.2059072142078227] | `5c4d8be596d189ca6053bf6ac3c8decafe337512ce6614d56c79f43f314b4960` | not met |
| 2 | 8 | 0.8363403049647729 | [0.7481568288450525, 0.9130706979128821] | 1.0 | [0.6305833524471807, 1.0] | `c3b88003d20779cb9938ae8a75ef26199db2dc2897f097b376ed2cbda69c418f` | not met |

k=3 was not viable (mean I about 0.028, accuracy 0). N=10000 was not started. k=2 accuracy was 1 on this n=8 draw, but mean I is 0.836 and the I interval lies entirely below 0.92, so that cell was not scaled up either. `k_max` is not claimed.

## Other levers checked in this session, not recorded as cells

Same `d=8192`, `M=1000`, soft cleanup, cosine-sum `I`, unless noted. These are small diagnostics, not protocol cells.

- Locked random init already fails k=3 inside `T=7`. Continuing that dynamic out to `T=40` on individual trials left mean I near 0.04 and the true factors' coefficient ranks in the hundreds. The miss is not fixed by spending the early-stop iterations that the locked runner returns.
- Power annealing, synchronous updates, coefficient top-k, and keeping the linear reconstruction (no intermediate phasor) did not recover k=3 from random or superposition init inside `T=7`.
- Starting on the true factors reaches min I about 0.962 after `T=7`. Phase noise of std 1.5 radians around those factors still finished near I 0.95; std 2.0 fell to about 0.02. The basin is real and the cleanup arithmetic works. Uniform superposition does not land in it for k=3.
- Freezing one true codeword and superposition-initializing the other two does separate that guess from false codewords (free-slot similarity to the nearest atom about 0.3 to 0.5 after two iterations, versus about 0.09 for false guesses) and the free argmaxes were the other true factors. Scanning the codebook for that guess is many cleanups. It is outside `T ≤ 7` and is not reported as a pass.
