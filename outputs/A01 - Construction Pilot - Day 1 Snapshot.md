# Factorio local-agent pilot: Day 1 results

The local model-to-game loop works on Oscar's RTX 5070 Ti. Two baseline attempts and one context intervention completed, but none produced iron plates. The C++/CUDA toolchain works, and real model tensors plus an unchanged-operator benchmark are saved for the required optimization experiment. Compute Sanitizer validation remains blocked pending permission for NVIDIA's Windows debugging interface setting.

## Execution and controls

The stack is Ubuntu 24.04.5 under WSL 2, native Docker Engine, PyTorch 2.11.0+cu128, Transformers 4.57.6, and Qwen3-4B-Instruct-2507 revision `cdbee75f17c01a7cc42f958dc650907174af0554`. Inference uses BF16, SDPA, batch size one, an 8,192-token total budget, and at most 1,024 new tokens. No fine-tuning or hosted model calls were used.

FLE source is pinned to `e2a829d22a635a9a111d21bf5523e09e903ae145`. Its Factorio 2.0.73 server image is pinned by digest. The lab scenario's embedded map seed is 2859378883, verified and logged in every included attempt. Factory starting-state hashes match. The first two exploratory attempts are preserved with exclusion notes because setup verification was incomplete.

The model returns a single JSON action through a restricted adapter covering eleven FLE tools. Generated text is not evaluated as Python. Reasoning occurs while paused. Movement temporarily runs the game at 10x for asynchronous pathfinding; actual ticks are recorded. Other actions add one game second. Evaluation uses a 60-second warm-up followed by two unattended 60-second windows, each verified as 3,600 actual ticks. The target is at least 16 automatically produced plates in each window. Positive throughput would still require a supply-chain audit.

## Measured attempts

| Attempt | Decisions | Failed actions | Plates in each window | Median response | Peak PyTorch allocation |
| --- | ---: | ---: | --- | ---: | ---: |
| Signatures-only baseline, seed 42 | 20 | 9 | 0, 0 | 1.70 s | 9.01 GiB |
| Signatures-only baseline, seed 43 | 32 | 10 | 0, 0 | 1.57 s | 9.00 GiB |
| Verified tool descriptions, seed 42 | 32 | 9 | 0, 0 | 1.57 s | 9.02 GiB |

All attempts had the same 32-decision maximum. The first baseline stopped when the model declared itself done; evaluation still failed. The others reached the decision limit. The intervention changed the prompt by adding actual controller descriptions. It enabled four successful coal insertions, but did not achieve the production target. Logs preserve invalid item/handle arguments, placement errors, repeated unsuccessful actions, and final factory states.

A wrapper-documentation bug caused the baseline to contain signatures and empty descriptions. The intervention reads the underlying controller methods and verifies that all eleven descriptions are present. This comparison tests a usability correction; it does not establish a novel memory method. Greedy decoding means different seeds are not independent sampling draws. One map, two baseline repetitions, and one intervention are insufficient for general performance or significance claims. Absolute ticks and movement duration vary and are logged. Memory figures exclude other applications' allocations.

## C++/CUDA evidence and remaining experiment

CUDA 12.8 compiled a 1,025-element vector-add program whose GPU output matched the C++ CPU reference. A separate inference profile captured 29,529 CUDA events. First-layer RMSNorm samples are BF16 with shapes `[1,1006,2560]` for prompt processing and `[1,1,2560]` for token generation, with epsilon `1e-6` and actual learned weights.

The unchanged installed RMSNorm passed a float64 numerical reference check with BF16 intermediate/output rounding (`rtol=0.02`, `atol=1e-5`). CUDA-event measurements used ten warm-ups and 100 samples: median 0.0876 ms for the prompt sample and 0.0946 ms for the token sample. These are reference operator measurements, not custom-kernel gains or whole-response speedups. Profile attribution is broader than this one normalization layer; matrix multiplication dominates the recognized GPU operators.

Day 2 should implement a bounded C++ binding and CUDA RMSNorm forward kernel, check correctness on these tensors and edge cases, then compare operator timing with this unchanged reference. Measure whole-response benefit only if integration is completed. No speedup is guaranteed. The numerical smoke test has not passed sanitizer checks: the sanitizer failed to initialize NVIDIA's Windows debugging interface, and automatic approval review rejected enabling its persistent system-wide registry setting without explicit permission. No GPU power, clock, or timeout settings were changed.

## Saved evidence

The Windows project contains `factorio-pilot/evidence/artifacts` for versions, profiles, reference tensors, and metrics, and `factorio-pilot/evidence/runs` for configurations, step logs, summaries, and final states. The exact signatures-only baseline sources are preserved under `factorio-pilot/source-snapshots/signature-baseline/tools`; their hashes match the recorded configurations. Active scripts are under `factorio-pilot/tools` and `factorio-pilot/setup`.

This is preliminary engineering evidence for a later study. It supports claims about local inference, instrumented agent evaluation, reproducibility controls, and toolchain preparation. It does not yet support claims of successful factory automation, CUDA optimization, or Oscar's independent mastery of the generated implementation.
