# Continuing the study

The public README explains the question and the measured findings. This guide identifies the code to change, the evidence to keep, and the checks needed before a new result can be compared with the old one.

## Find the right layer

| Location | Purpose |
| --- | --- |
| [`factorio-pilot/tools/`](../factorio-pilot/tools/) | Current Python controllers, validated game tools, checks, and reports. `maintenance_agent.py` is the active maintenance controller; `run_agent.py` belongs to the earlier construction pilot. |
| [`factorio-pilot/cuda/`](../factorio-pilot/cuda/) | The active C++ binding and CUDA RMSNorm kernel. Changes here invalidate the recorded native review. |
| [`factorio-pilot/setup/`](../factorio-pilot/setup/) | Launch and installation scripts. The maintenance launcher accepts `FACTORIO_PILOT_HOME`; older scripts still contain paths from the original host. |
| [`factorio-pilot/evidence/runs/`](../factorio-pilot/evidence/runs/) | Per-run configuration, action trace, summary, and observed final state. |
| [`factorio-pilot/evidence/artifacts/`](../factorio-pilot/evidence/artifacts/) | Environment pins, captured operator inputs, numerical checks, sanitizer receipts, and timing samples. |
| [`factorio-pilot/source-snapshots/`](../factorio-pilot/source-snapshots/) | Frozen copies of code that produced earlier results. Read these for provenance; edit active source instead. |
| [`outputs/`](../outputs/) | Ordered agent (`A##`) and kernel (`K##`) reports, the native source review, and the pilot protocol. Preserve an existing measurement when adding a new one. |
| [`scripts/`](../scripts/) | Evidence checks and packaging helpers, including the CPU-only maintenance verifier. |

The [runtime README](../factorio-pilot/README.md) begins with the original two-minute construction pilot and later documents guided construction, logistics, and the 20-minute maintenance task. Those are different protocols. A command in a dated report reproduces that report's host setup; it is not a portable default for every checkout.

## Report naming

Use `A## - Stage - Record.md` for Factorio agent work and `K## - Operator - Record.md` for kernel work. Give a new experiment stage the next number in its track. Keep related records under one number: `A01` has a Day 1 snapshot and final pilot results; `A04` has the maintenance results and a separate offline decision diagnostic. The prefix groups evidence by protocol, while the final part names the kind of record. The native source review is an engineering review rather than a measured iteration, so it remains unnumbered.

## Add a result without changing an old one

1. Choose the experiment and read its report, run configuration, and evaluated source snapshot. Record what changes: task fixture, controller, context policy, model, tools, decoding, cadence, or hardware.
2. Change active source in `tools/` or `cuda/`. Keep historical snapshots, configurations, source hashes, and raw measurements byte-for-byte intact. Give a new protocol or run its own name and timestamped evidence directory.
3. Check the task with an idle or scripted control where reachability matters. Keep construction, logistics, maintenance, and offline diagnostics in separate reports. An offline proposed action is not an executed game result.
4. Run the relevant CPU checks. Before **any** GPU/model run, fully inspect all project-authored C++/CUDA sources and confirm the exact-hash review gate described in [CONVENTIONS.md](../CONVENTIONS.md) and the [native source review](../outputs/CUDA%20and%20C%2B%2B%20Source%20Review.md). A regenerated manifest is not a review.
5. Add a report with the fixture, controls, source hashes, outcome definition, sample count, timing scope, and links to the new trace. Say whether a run failed, survived its horizon, or stopped at a budget. Do not pool results from different task versions.

For an immediate check from any clone, run `python scripts/verify_maintenance_evidence.py` from the repository root. It uses only the Python standard library and reads the retained maintenance summaries and JSONL traces. The full CPU test suite requires the pinned project environment described in the [runtime README](../factorio-pilot/README.md). Live Factorio and Qwen runs additionally require the external FLE installation, game server, model snapshot, and runtime artifacts; cloning this repository alone does not recreate them.

## Planned K02: integrated RMSNorm run

The [K01 benchmark](../outputs/K01%20-%20RMSNorm%20-%20Reviewed%20Benchmark.md) measures one standalone operator. The maintenance agent still uses Qwen's original PyTorch RMSNorm. K02 will test whether using the custom operator inside Qwen reduces complete response and episode wall time while preserving useful model behavior. No integrated speedup has been measured yet.

1. Save a matched baseline with the pinned Qwen revision, BF16 precision, hardware, decoding settings, and representative maintenance prompts. Record model and source hashes. Keep model loading and extension compilation outside warm inference timing.
2. Add an optional backend that replaces only supported RMSNorm calls (contiguous BF16 CUDA inputs with 2,560 features); leave other calls on the original implementation and record how many modules were replaced. Fully review every project-authored C++/CUDA source before a GPU run, then repeat matching correctness and sanitizer checks for any changed native code.
3. On the same saved prompts, compare original and custom backends for finite logits, numerical differences, greedy token sequences, valid JSON actions, prompt processing time, token generation time, complete response latency, and GPU memory. Record any changed action rather than assuming equivalent behavior.
4. Alternate the order of warmed baseline and custom measurements across repeated batches, preserving raw timings and the exact inputs. Report the operator result separately from whole-model results.
5. Only after the offline checks, run both backends on the same maintenance fixture and decision cadence. Save each run's configuration, actions, production windows, failure or survival endpoint, and total wall time. Compare outcomes and speed separately; do not infer an episode speedup from K01's operator ratio.

Publish a `K02 - RMSNorm - Integrated Inference Results.md` report only after these runs, with source hashes, sample counts, timing scope, and links to the new evidence. Keep K01 and the earlier agent episodes unchanged.

## Move work from a private checkout

This public repository has clean history. If development starts in a private checkout, review the specific changed files and copy an approved patch or artifact set onto a branch based on this public `main`. Do not merge or push the private repository's history. Check filenames and contents for credentials, correspondence, local-only artifacts, and third-party material before pushing. Preserve exact evaluated bytes and hashes when transferring evidence, and keep model weights and game binaries outside Git.

The standalone RMSNorm speedups describe one operator against the installed eager CUDA reference. Integration into Qwen, whole-model speedup, and maintenance memory/retrieval comparisons still need separate implementations and measurements. The project currently has no license granting reuse of its original source or evidence.
