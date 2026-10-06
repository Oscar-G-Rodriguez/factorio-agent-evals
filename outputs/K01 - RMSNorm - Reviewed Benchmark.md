# Reviewed RMSNorm benchmark

The reviewed active C++ binding and CUDA kernel were rebenchmarked on October 6, after matching numerical checks and all four sanitizer tools passed. The prior benchmark was preserved before rerunning. The fresh benchmark again passed all 25 correctness cases.

| Captured operation | Reference median across batches | Custom median across batches | Median within-batch speedup |
| --- | ---: | ---: | ---: |
| Prompt processing, 1006 rows | 0.09282 ms | 0.01776 ms | 5.21× |
| Token generation, one row | 0.09278 ms | 0.01909 ms | 4.80× |

Reference is the installed eager Qwen RMSNorm operator already executing on CUDA. This is not a CPU-to-GPU comparison. Both functions allocate outputs and use resident BF16 GPU inputs. Timing uses CUDA events with wrapper launch gaps included, 10 warm-ups and 100 alternating pairs in each of three batches. Median ratios are computed within batches; a ratio of the independently summarized medians need not equal the reported paired speedup. Raw samples and per-batch p95 values remain in `factorio-pilot/evidence/artifacts/rmsnorm-custom-benchmark.json`; the full log is `reviewed-rmsnorm-benchmark.txt`. These captured shapes are not the longest maintenance prompts and do not establish batched-inference performance.

The C++ source SHA-256 is `566fed2c0da73d12dca820a7cd727354942f302ca39b6c52fb966e08a15650b9`; CUDA source SHA-256 is `6e8f69612ac5537ae4781df3b7034e63c9c1b492e11c72f110f97449405466c1`. They match the reviewed/sanitized sources. GPU was RTX 5070 Ti with the pinned project runtime. Reproduction: run `factorio-pilot/setup/run-rmsnorm.sh` through the existing WSL virtual environment after the native-review and matching-correctness gate passes. Preserve prior result files before rerunning.

Qwen maintenance still uses the original backend. Whole-model acceleration is unmeasured until the custom operator is integrated and compared on identical prompts. In the earlier maintenance episode, generation consumed 73.91 of 179.76 wall seconds; the remaining time includes simulation, tool/observation calls and prompt processing outside the generation timer. As a hypothetical, halving complete generation time would reduce that episode's wall time to about 142.80 seconds, a 1.26× overall speedup. That example is not a prediction that optimizing RMSNorm halves generation time.
