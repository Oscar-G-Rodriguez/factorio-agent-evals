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

## Planned K02: integrated RMSNorm run

The [K01 benchmark](../outputs/K01%20-%20RMSNorm%20-%20Reviewed%20Benchmark.md) measures one standalone operator. The maintenance agent still uses Qwen's original RMSNorm. The [inference acceleration design](Inference%20Acceleration%20Design.md) is the canonical proposal for guarded integration, restoration, an optimized compiled-reference baseline, exact-prefix cache reuse and timing boundaries. The [decision record](decisions/0001-controlled-inference-acceleration.md) explains why these changes are separated from policy improvements.

The proposed integration changes only supported full-width norm calls, preserves the original forward for unsupported calls, and keeps the existing game cadence. Freeze parameters for every inference condition because the forward-only native binding rejects weights requiring gradients. Validate identical saved prompts and generated actions before comparing application timing. Existing source review and matching correctness gates remain mandatory.

Experiments are sequential. The acceleration design is being settled before further execution; no integrated, compiled-reference or prefix-cache measurements exist. A future measured K02 report belongs at `outputs/K02 - RMSNorm - Integrated Inference Results.md` and must record hashes, coverage, numerical/action checks, raw timing samples and the full timing scope. Cache reuse receives a separately identified comparison after its implementation is validated. Preserve K01 and the earlier agent episodes unchanged.

## Move work from a private checkout

This public repository has clean history. If development starts in a private checkout, review the specific changed files and copy an approved patch or artifact set onto a branch based on this public `main`. Do not merge or push the private repository's history. Check filenames and contents for credentials, correspondence, local-only artifacts, and third-party material before pushing. Preserve exact evaluated bytes and hashes when transferring evidence, and keep model weights and game binaries outside Git.

The standalone RMSNorm speedups describe one operator against the installed eager CUDA reference. Integration into Qwen, whole-model speedup, and maintenance memory/retrieval comparisons still need separate implementations and measurements. Project-authored repository contents are available under the [MIT License](../LICENSE); external components retain their own terms.
