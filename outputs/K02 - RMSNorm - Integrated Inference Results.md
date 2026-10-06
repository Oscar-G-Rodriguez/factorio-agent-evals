# K02 - RMSNorm - Integrated inference results

The custom C++/CUDA operator was connected to Qwen through an instance-local Python adapter. The adapter preserves existing weights and restores original forwards after each condition. This record covers offline saved-prompt inference; no Factorio actions were executed. Custom dispatch produced 1.11–1.17× eager/custom paired median response ratios across these five prompts. The compiled reference varied by prompt; the table below retains gains and slowdowns.

## Methods

Five predeclared decisions from the retained A04 episode represent early play, fuel demand, full carrying inventory, a recent collection failure and a late decision. The prompt manifests retain exact messages, source steps and hashes. Qwen3-4B-Instruct-2507 uses the pinned revision, BF16, SDPA, greedy generation, an 8,192-token context limit and 256-token output budget with the existing complete-JSON stopping rule. All parameters are frozen for inference.

Only 2,560-feature full-width norms are eligible. Attention-head norms remain on the original implementation. Known unsupported inputs use the original forward; native/load errors stop the custom condition. Diagnostics record actual dispatch separately from timing. All five native files were re-inspected and their hash gate passed. A fresh bounded operator suite passed all 25 cases before model integration; no native sources or GPU settings were changed. Earlier matching sanitizer evidence remains operator evidence.

The acceptance gate requires finite checked logits and identical greedy tokens/actions on this fixed manifest. Logit differences are retained as diagnostics. Agreement on five prompts is not universal numerical or behavioral equivalence.

## Validation

| Run | Endpoint | Checked responses | Passing responses |
| --- | --- | ---: | ---: |
| `K02-integrated-20261006T082739Z` | `offline_validation_passed` | 10 | 10 |
| `K02-integrated-20261006T082927Z` | `offline_benchmark_complete` | 15 | 15 |

| Run | Custom norm modules | Custom calls observed | Maximum prefill logit difference |
| --- | ---: | ---: | ---: |
| `K02-integrated-20261006T082739Z` | 73 | 10366 | 1.125 |
| `K02-integrated-20261006T082927Z` | 73 | 10366 | 1.125 |

Logit differences are measured on the final prefill position, not every vocabulary score at every input position. The forced eight-token decode diagnostic also checks finite logits. Generated JSON envelopes were validated; parsed-action agreement is an offline result and does not establish executed episode improvement.

## Timing and optimized reference

Backend switching and adapter installation occur outside the response timer; the live controller installs its adapter once at loading. Complete response timing includes prompt tokenization, transfers, greedy generation, decoding and JSON-envelope validation, with synchronization at response boundaries. Loading/build costs are separate. First-pass validation latencies may contain cold initialization or compilation and are not warm benchmark estimates. The forced-token GPU segments in validation are single diagnostic samples and are not latency distributions.

| Source step | Prompt tokens | Generated tokens |
| ---: | ---: | ---: |
| 0 | 1220 | 18 |
| 17 | 7501 | 21 |
| 23 | 7487 | 22 |
| 24 | 7461 | 18 |
| 43 | 7121 | 18 |

Warm response measurements use ten warm-ups and three blocks of 30 alternating samples per backend and prompt. Median ratios are calculated from matched within-block medians. Raw samples retain tokens and parsed actions; the benchmark stops if token agreement changes.

| Run / step | Backend | Samples | Median response ms | p95 ms | Eager/backend ratio |
| --- | --- | ---: | ---: | ---: | ---: |
| `K02-integrated-20261006T082927Z` / 0 | eager | 90 | 761.149 | 898.724 | 1.000× |
| `K02-integrated-20261006T082927Z` / 0 | custom | 90 | 647.722 | 767.578 | 1.171× |
| `K02-integrated-20261006T082927Z` / 0 | compiled | 90 | 537.311 | 568.902 | 1.401× |
| `K02-integrated-20261006T082927Z` / 17 | eager | 90 | 1697.083 | 1923.563 | 1.000× |
| `K02-integrated-20261006T082927Z` / 17 | custom | 90 | 1526.920 | 1763.470 | 1.110× |
| `K02-integrated-20261006T082927Z` / 17 | compiled | 90 | 2649.131 | 2844.118 | 0.643× |
| `K02-integrated-20261006T082927Z` / 23 | eager | 90 | 1711.937 | 1973.867 | 1.000× |
| `K02-integrated-20261006T082927Z` / 23 | custom | 90 | 1532.875 | 1727.705 | 1.115× |
| `K02-integrated-20261006T082927Z` / 23 | compiled | 90 | 2708.044 | 2915.179 | 0.637× |
| `K02-integrated-20261006T082927Z` / 24 | eager | 90 | 1601.198 | 1714.727 | 1.000× |
| `K02-integrated-20261006T082927Z` / 24 | custom | 90 | 1436.226 | 1535.878 | 1.117× |
| `K02-integrated-20261006T082927Z` / 24 | compiled | 90 | 2501.534 | 2603.589 | 0.640× |
| `K02-integrated-20261006T082927Z` / 43 | eager | 90 | 1525.691 | 1636.464 | 1.000× |
| `K02-integrated-20261006T082927Z` / 43 | custom | 90 | 1370.684 | 1485.484 | 1.114× |
| `K02-integrated-20261006T082927Z` / 43 | compiled | 90 | 2346.917 | 2501.165 | 0.649× |

`K02-integrated-20261006T082927Z` attempted the original model forward compiled with Inductor, default mode and dynamic shapes. The first compiled natural response took 234.19 seconds, including cold compilation. Compiler counters and all validation responses remain in the raw record. A compiled label alone does not prove speedup.

## Evidence and reproduction

The fresh [25-case native check](../factorio-pilot/evidence/artifacts/K02-fresh-rmsnorm-correctness.json) preceded model loading. All 30 CPU unit tests passed, including five adapter tests covering guards, unsupported-input fallback and restoration. Launcher syntax, retained maintenance evidence and 112 local documentation links also passed. Run `python scripts/verify_k02_evidence.py` from any clone for a CPU-only audit of export hashes, source hashes, frozen prompts, coverage and every retained response/sample.

- [K02-integrated-20261006T082739Z results](../factorio-pilot/evidence/runs/K02-integrated-20261006T082739Z/results.json), [frozen prompts](../factorio-pilot/evidence/runs/K02-integrated-20261006T082739Z/prompt-manifest.json), and [evaluated Python source](../factorio-pilot/evidence/runs/K02-integrated-20261006T082739Z/source/).
- [K02-integrated-20261006T082927Z results](../factorio-pilot/evidence/runs/K02-integrated-20261006T082927Z/results.json), [frozen prompts](../factorio-pilot/evidence/runs/K02-integrated-20261006T082927Z/prompt-manifest.json), and [evaluated Python source](../factorio-pilot/evidence/runs/K02-integrated-20261006T082927Z/source/).

From the repository root in the configured Linux environment:

```bash
export FACTORIO_PILOT_HOME="${FACTORIO_PILOT_HOME:-$HOME/factorio-pilot}"
bash factorio-pilot/setup/run-integrated-rmsnorm.sh --phase validate
bash factorio-pilot/setup/run-integrated-rmsnorm.sh --phase benchmark --include-compiled
```

The runtime must contain the pinned model and matching operator correctness artifact. Read the [native review](CUDA%20and%20C%2B%2B%20Source%20Review.md) before GPU execution. Each run writes fresh K02 evidence; preserve old artifacts before repeating native checks. Native row bounds, unsupported-call handling and the [acceleration design](../docs/Inference%20Acceleration%20Design.md) remain applicable.

## Limits

This uses five states from one development fixture, not held-out fixtures or live episodes. Warm total-response timing is distinct from the single prefill/forced-decode diagnostic samples. Prefix-cache reuse and training remain separate work. The forward-only kernel supplies no backward path. No episode-wall-time speedup or improved factory maintenance follows from these offline measurements.
