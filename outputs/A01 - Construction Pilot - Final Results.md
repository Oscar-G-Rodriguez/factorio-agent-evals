# Factorio local agent pilot preliminary results

The local Qwen agent and its observed-fact memory were evaluated on an RTX 5070 Ti. All four model runs produced zero iron plates. A scripted control verified the production target is reachable. The custom C++/CUDA RMSNorm passed numerical checks and was benchmarked against the installed operator; whole-model benefit was not measured and sanitizer validation remains pending. These are preliminary engineering results for a future longer-running study.

## Factory and context experiment

The scripted reachability control produced 38, 36 iron plates in its two 60-second windows. It inserted only supplied coal, verified pause/tick control and pickup handle invalidation, and is excluded from model results. Final furnace ore/plate inventories and the action trace support automatic drill-to-furnace supply.

| Context | Decisions | Failed actions | Plates in windows | Median response | Input tokens | Peak allocated GPU memory |
| --- | ---: | ---: | --- | ---: | ---: | ---: |
| history | 15 | 5 (33.3%) | [0, 0] | 1.20 s | 55,368 | 8.88 GiB |
| history | 32 | 19 (59.4%) | [0, 0] | 1.42 s | 171,949 | 9.00 GiB |
| structured-memory | 32 | 17 (53.1%) | [0, 0] | 1.27 s | 178,752 | 9.01 GiB |
| structured-memory | 20 | 6 (30.0%) | [0, 0] | 1.33 s | 95,423 | 9.01 GiB |

Both conditions use the same corrected tools, model revision, starting-state hash, map seed, source hashes, 32-decision budget, greedy decoding, BF16 inference and token limits. The only condition change is a memory supplement capped at 512 tokenizer tokens. It retains last-observed equipment facts and up to four failures, discarding complete old records when necessary; picked-up handles are invalidated. It does not access hidden state or use another model.

Neither context condition reached the production target. The small sample and differing trajectories do not establish a reliable memory benefit.

History messages dropped per included run: history=0, history=46, structured-memory=38, structured-memory=16. Maximum memory supplement per run: 0, 0, 452, 452 tokens.

Output token totals per included run: 341, 6657, 555, 437. Responses reaching the 1,024-token cap: 0, 6, 0, 0. Failures are separated by exception class in the saved metrics.

Each evaluation pauses the game during reasoning, allows asynchronous movement with actual ticks logged, warms up for 60 simulated seconds, then measures two unattended 3,600-tick windows. Success requires at least 16 plates in both windows and a supply-chain audit. Positive throughput without that audit remains unconfirmed.

## C++ and CUDA experiment

The Python-callable C++ wrapper checks shape, dtype, device, contiguity and inference-only usage. The CUDA kernel normalizes each 2,560-feature row with one 256-thread block, FP32 reduction and explicit BF16 rounding before learned-weight multiplication. It follows the current PyTorch stream and does not modify the model.

All 16 numerical, boundary and stream checks passed. Captured model tensors and synthetic inputs were compared with the installed Qwen operator and a float64 reference with BF16 rounding, using rtol=0.02 and atol=1e-5. This allows small numerical differences; it does not promise identical model token choices.

| Phase | Reference median across batches | Custom median across batches | Median paired speedup |
| --- | ---: | ---: | ---: |
| prefill | 0.1055 ms | 0.0172 ms | 5.83x |
| decode | 0.1195 ms | 0.0218 ms | 5.12x |

Timing uses alternating reference/custom order, ten warm-ups per implementation and 100 pairs in each of three batches. Both operators include output allocation; inputs already reside on the GPU. CUDA-event samples include possible launch gaps. Raw samples and p95 values are saved. Operator gains do not establish faster complete model responses; full-model integration is deferred.

## Limits and next experiments

One model, one map and two greedy repetitions per condition support descriptive findings only. Absolute game ticks and movement timing can differ and appear in observations, so repeated runs do not receive bit-identical prompts. Greedy repetitions are not independent sampling draws. Prior signatures-only runs remain archived separately because they used a different tool contract. Some FLE warnings reported blocked output despite actual ore transfer; throughput and final inventories are stronger evidence than those warnings.

An earlier memory attempt stopped with a CUDA unknown error during ordinary Qwen inference before a final production measurement. It is excluded from the comparison, with its partial log and explicit quality note retained. Its preceding complete history run is also archived outside the fresh four-run comparison. The custom kernel was not compiled or loaded at the interruption; the underlying cause remains unconfirmed. A fresh-process CUDA numerical check passed before retrying. The first custom-kernel build also failed because a broad PyTorch header required an unavailable sparse-library header; using the narrower CUDA stream header resolved that build dependency.

Next: report elapsed ticks from reset to reduce incidental prompt differences, and test concise valid tool-call examples against the observed item/handle confusion. Then use longer runs that force history truncation and explicit recovery tasks. More map seeds, additional models and whole-model kernel integration follow after that. If no history was dropped in a run, its memory-retention benefits remain untested even though the memory supplement was evaluated.

Compute Sanitizer remains blocked by the Windows debugging interface. Automatic approval review rejected its persistent system-wide registry change without explicit permission. Numerical checks passed, but sanitizer validation is incomplete. No power, clock or timeout settings were changed.

The implementation was produced with Codex assistance. Independent mastery requires Oscar to explain, modify and rerun the important pieces; code generation alone does not demonstrate it.

## Reproduction and evidence

See `factorio-pilot/README.md` for commands and pinned dependencies. `evidence/artifacts/pilot-results.json` contains all metrics; individual run folders contain prompts, configurations, decisions, errors and factory states. `source-snapshots/context-pilot` preserves the evaluated source.

## Sources

- [Factorio Learning Environment](https://github.com/JackHopkins/factorio-learning-environment) and [original FLE paper](https://arxiv.org/abs/2503.09617). The environment is prior work; this pilot evaluates a small local integration.
- [Qwen3 model](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507).
- [PyTorch C++ and CUDA operators](https://docs.pytorch.org/tutorials/advanced/cpp_custom_ops.html).
- [NVIDIA Compute Sanitizer](https://docs.nvidia.com/compute-sanitizer/ComputeSanitizer/index.html#windows-specific-behavior).
