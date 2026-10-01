# Adl bucket-triple falsifier — not a pass

This is not a locked-grid cell and it is not a pass. `CONSTITUTION_v1.3.md`, the default `resonator()` / `run_trial()` path, and `results/execution_record.json` were not modified. The code is `core/bucket_triple.py` at `11caad8d0382403048076d7d2d76a3b5696f88b9`. Later commits on this branch are Phase I checkpoints; they do not change that file.

## Procedure

Assumption under test: `s` is one component-wise product of three distinct codebook phasors. `gamma = 0`, so that product is exact.

`d = 8192`, `M = 1000`, bucket size 5 so `B = 200`, `k = 3`, `T_max = 7`. Codebook seed `20260930` (same family as the locked runner). Trial seed `20261002`. Trial `i` uses `SeedSequence([20261002, i]).spawn(1 + T_max)`: child 0 draws the three generators, and each later child is an independent hash. Bootstrap seed `20260930`, `B = 10000`, used only if every usable trial has a retrieval `I`.

Each hash partitions the codebook into 200 buckets of 5. The bucket vector is the linear sum of its codewords. Those sums are not phasor-projected. Every unordered triple of distinct buckets (1,313,400 triples; the score is invariant to order) is scored by

```
I = (1/d) sum_j cos(phase(s_j * conj(v_b,j) * conj(v_g,j) * conj(v_d,j)))
```

A zero modulus is a projection fault, never phase 0. There were none. Reported scores are that literal mean. A float32 phase screen only proposes candidates; on this run it never fell back, and trial 0's winner and best impostor matched a full float64 scan of all 1,313,400 triples.

A hash is one step. While the winning score is below 0.7 and steps remain, the next step is an independent rehash, not cleanup. A winner at or above 0.7 would spend one remaining step on an exact scan of one codeword from each winning bucket, scored by the locked cosine-sum. Retrieval `I` is the locked designated-factor cosine-sum (`benchmark_metrics.invertibility`) against that recovery. No trial cleared 0.7, so that scan never ran, and no retrieval `I` was invented.

## Measured n = 200

Machine record: `results/bucket_triple_falsifier.json`. First trial 20.03 s. Wall time about 71.6 min (ended 7:14 AM ET). Status is for these 200 trials only.

| quantity | value |
|---|---|
| usable trials | 200 |
| projection faults | 0 |
| retrieval hits | 0 |
| retrieval accuracy | 0 |
| Clopper-Pearson 95% CI | [0, 0.018275340355136283] |
| accuracy CI low | 0 |
| trials with a recovered factor | 0 |
| mean I | null (not defined) |
| mean I bootstrap CI | null |
| hashes per trial | 7 |
| rehash used | 200 / 200 |
| extra hashes beyond the first | 1200 |
| threshold 0.7 cleared | 0 |
| max winning I on any hash | 0.09481187845247668 |
| mean final winning I | 0.06386317348706477 |
| final triple contains all three generators | 199 / 200 |
| bucket collisions | 1 (trial 86, seed `[20261002, 86]`, buckets `[199, 174, 174]`) |
| gap on the 199 non-collision trials | all positive |

Gap = generator-triple `I` minus best impostor `I`. On the 199 trials with three distinct generator buckets: mean 0.025608189067901015, std 0.008514177368404305, min 0.0026620697280123826, median 0.025450953540866954, max 0.05672833290202195, negative gaps 0. The collision trial has no single generator triple, so its gap is null. Its winning triple did not cover both occupied buckets.

## Floors

A pass needs lower Clopper-Pearson accuracy >= 0.95 and lower bootstrap CI of mean I >= 0.92, on the n actually run. Accuracy CI low is 0. Mean I has no bootstrap interval because cleanup never ran. `floors_met` is false. `status` is `not_a_pass`.

The bucket score does separate the true triple from impostors (positive gap on every non-collision trial), but the absolute score stays near 0.06, far below 0.7. The gate therefore spends the whole budget on rehashes. That is a failure of this procedure at the real size, not a small-n pass.
