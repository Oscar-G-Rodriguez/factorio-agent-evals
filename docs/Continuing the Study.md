# Continuing the study

The public README explains the question and the measured findings. This guide identifies the code to change, the evidence to keep, and the checks needed before a new result can be compared with the old one.

## Find the right layer

| Location | Purpose |
| --- | --- |
| [`factorio-pilot/tools/`](../factorio-pilot/tools/) | Current Python controllers, validated game tools, checks, and reports. `maintenance_agent.py` is the active maintenance controller; `run_agent.py` belongs to the earlier construction pilot. |
| [`factorio-pilot/cuda/`](../factorio-pilot/cuda/) | The active C++ binding and CUDA RMSNorm kernel. Changes here invalidate the recorded native review. |
| [`factorio-pilot/setup/`](../factorio-pilot/setup/) | Launch and installation scripts. Launchers locate this checkout and accept `FACTORIO_PILOT_HOME` for the Linux runtime. |
| [Saved-run index](../factorio-pilot/evidence/runs/README.md) | Folder naming, stage-to-run mapping, configurations, action traces, summaries, and partial records. |
| [`factorio-pilot/evidence/artifacts/`](../factorio-pilot/evidence/artifacts/) | Environment pins, captured operator inputs, numerical checks, sanitizer receipts, and timing samples. |
| [`factorio-pilot/source-snapshots/`](../factorio-pilot/source-snapshots/) | Frozen copies of code that produced earlier results. Read these for provenance; edit active source instead. |
| [`outputs/`](../outputs/) | Ordered agent (`A##`) and kernel (`K##`) reports, the native source review, and the pilot protocol. Preserve an existing measurement when adding a new one. |
| [`scripts/`](../scripts/) | Evidence checks and packaging helpers, including the CPU-only maintenance verifier. |

The [runtime README](../factorio-pilot/README.md) begins with the original two-minute construction pilot and later documents guided construction, logistics, and the 20-minute maintenance task. Those are different protocols. A command in a dated report reproduces that report's host setup; it is not a portable default for every checkout.

## Report naming

Use `A## - Stage - Record.md` for Factorio agent work and `K## - Operator - Record.md` for kernel work. Give a new experiment stage the next number in its track. Keep related records under one number: `A01` has a Day 1 snapshot and final pilot results; `A04` has the maintenance results and a separate offline decision diagnostic. The prefix groups evidence by protocol, while the final part names the kind of record. The native source review is an engineering review rather than a measured iteration, so it remains unnumbered.

Raw run folders use `A##-<condition>-<UTC timestamp>[-seedN]`; future kernel runs may use `K##` in the same form. The [saved-run index](../factorio-pilot/evidence/runs/README.md) maps the renamed historical folders to reports and explains legacy IDs inside their unchanged contents. New run creators and the evidence exporter apply the stage prefix. Preserve the same run ID in logs, summaries, and report links for each future record.

## Add a result without changing an old one

1. Choose the experiment and read its report, run configuration, and evaluated source snapshot. Record what changes: task fixture, controller, context policy, model, tools, decoding, cadence, or hardware.
2. Change active source in `tools/` or `cuda/`. Keep historical snapshots, configurations, source hashes, and raw measurements byte-for-byte intact. Give a new protocol or run its own name and timestamped evidence directory.
3. Check the task with an idle or scripted control where reachability matters. Keep construction, logistics, maintenance, and offline diagnostics in separate reports. An offline proposed action is not an executed game result.
4. Run the relevant CPU checks. Before **any** GPU/model run, fully inspect all project-authored C++/CUDA sources and confirm the exact-hash review gate described in [CONVENTIONS.md](../CONVENTIONS.md) and the [native source review](../outputs/CUDA%20and%20C%2B%2B%20Source%20Review.md). A regenerated manifest is not a review.
5. Add a report with the fixture, controls, source hashes, outcome definition, sample count, timing scope, and links to the new trace. Say whether a run failed, survived its horizon, or stopped at a budget. Do not pool results from different task versions.

For an immediate check from any clone, run `python scripts/verify_maintenance_evidence.py` from the repository root. It uses only the Python standard library and reads the retained maintenance summaries and JSONL traces. The full CPU test suite requires the pinned project environment described in the [runtime README](../factorio-pilot/README.md). Live Factorio and Qwen runs additionally require the external FLE installation, game server, model snapshot, and runtime artifacts; cloning this repository alone does not recreate them.

## K02: integrated RMSNorm evidence

The [K01 benchmark](../outputs/K01%20-%20RMSNorm%20-%20Reviewed%20Benchmark.md) measures one standalone operator. [K02](../outputs/K02%20-%20RMSNorm%20-%20Integrated%20Inference%20Results.md) connects it to 73 full-width Qwen norms and compares offline saved-prompt responses with eager PyTorch and an Inductor reference. Attention-head norms remain unchanged. Five saved states produced identical greedy tokens and parsed actions; logit differences are retained rather than treated as numerical identity.

`tools/qwen_rmsnorm_backend.py` owns guarded dispatch and restoration. `tools/check_integrated_rmsnorm.py` freezes the prompt manifest, validates candidates before timing and writes fresh K02 run directories. The [runtime README](../factorio-pilot/README.md#integrated-rmsnorm-offline-evaluation) gives exact entry points. Native inspection, hash and matching correctness gates remain mandatory. New native files or edits require inspection before updating a manifest.

The maintenance runner defaults to `--inference-backend pytorch`; `custom-rmsnorm` is opt-in for model controllers. No live episode was run with that option. Experiments remain sequential. The [acceleration design](Inference%20Acceleration%20Design.md) specifies the unchanged contract and a subsequent exact-prefix cache comparison, while the [decision record](decisions/0001-controlled-inference-acceleration.md) preserves the choice. Prefix reuse, warm GPU-phase distributions, time to first token and episode speedup remain unmeasured. Keep those results separately identified and preserve K01/A01–A04 evidence.

## Move work from a private checkout

This public repository has clean history. If development starts in a private checkout, review the specific changed files and copy an approved patch or artifact set onto a branch based on this public `main`. Do not merge or push the private repository's history. Check filenames and contents for credentials, correspondence, local-only artifacts, and third-party material before pushing. Preserve exact evaluated bytes and hashes when transferring evidence, and keep model weights and game binaries outside Git.

The standalone RMSNorm speedups describe one operator against the installed eager CUDA reference. K02 measures integrated offline response latency; matched gameplay throughput and maintenance memory/retrieval comparisons still require separate measurements. Project-authored repository contents are available under the [MIT License](../LICENSE); external components retain their own terms.
