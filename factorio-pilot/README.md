# Factorio local agent pilot

This pilot evaluates one local Qwen model controlling Factorio, a bounded observed-fact memory supplement, and a custom C++/CUDA RMSNorm operator. It targets two unattended minutes of automated iron production. Failed agent runs and kernel slowdowns remain valid results. Full-model kernel integration is deferred.

## Environment

Execution uses Ubuntu 24.04.5 under WSL 2 on the Windows RTX 5070 Ti host. Native Docker Engine runs the local Factorio server. Python 3.12.3 and project packages live in `/home/osci2/factorio-pilot/.venv`. Linux project artifacts are exported to this Windows workspace; model weights remain in Linux storage.

Pinned dependencies:

| Component | Version |
| --- | --- |
| Qwen/Qwen3-4B-Instruct-2507 | `cdbee75f17c01a7cc42f958dc650907174af0554` |
| FLE source | `e2a829d22a635a9a111d21bf5523e09e903ae145` |
| Factorio server | 2.0.73 |
| Server image digest | `sha256:6471fbfb7eab3abf55bb53fed632606ecf17bf930891bccddff724afab9ed94c` |
| PyTorch | 2.11.0+cu128 |
| Transformers | 4.57.6 |
| Accelerate | 1.15.0 |
| CUDA compiler | 12.8.93 |

Complete package versions are in `evidence/artifacts/requirements-tested.txt`. The saved lab scenario has actual map seed 2859378883. Evaluated source and starting-state hashes are recorded per run. FLE uses structured tools; sprite images are unnecessary for this pilot. The installed graphical client is optional.

## Reproduce on this host

Run these commands from PowerShell in the project parent (`igni`). They use root only for the Docker restart; agent and reference scripts run as ordinary Linux user `osci2`.

```powershell
wsl -d Ubuntu-24.04 -u osci2 -- /home/osci2/factorio-pilot/.venv/bin/python -m unittest discover -s /mnt/c/Users/osci2/Documents/Codex/2026-10-05/igni/factorio-pilot/tools -p 'test_*.py'
wsl -d Ubuntu-24.04 -u root -- bash /mnt/c/Users/osci2/Documents/Codex/2026-10-05/igni/factorio-pilot/setup/run-reference.sh
wsl -d Ubuntu-24.04 -u root -- bash /mnt/c/Users/osci2/Documents/Codex/2026-10-05/igni/factorio-pilot/setup/run-context-experiment.sh
wsl -d Ubuntu-24.04 -u osci2 -- bash /mnt/c/Users/osci2/Documents/Codex/2026-10-05/igni/factorio-pilot/setup/run-rmsnorm.sh
wsl -d Ubuntu-24.04 -u osci2 -- /home/osci2/factorio-pilot/.venv/bin/python /mnt/c/Users/osci2/Documents/Codex/2026-10-05/igni/factorio-pilot/tools/report_pilot.py
wsl -d Ubuntu-24.04 -u osci2 -- /home/osci2/factorio-pilot/.venv/bin/python /mnt/c/Users/osci2/Documents/Codex/2026-10-05/igni/factorio-pilot/tools/export_evidence.py
```

Run each command after the preceding one completes. Avoid other GPU work during the RMSNorm benchmark. New agent runs get timestamped folders; repeating the experiment preserves old evidence. `report_pilot.py` selects the most recent two runs of each context policy with matching frozen source hashes and checks comparison controls. Reference and kernel artifact filenames are regenerated; archive them before rerunning if preserving the original measurement files is necessary.

For a read-only progress snapshot while a run is active:

```powershell
wsl -d Ubuntu-24.04 -u osci2 -- /home/osci2/factorio-pilot/.venv/bin/python /mnt/c/Users/osci2/Documents/Codex/2026-10-05/igni/factorio-pilot/tools/show_progress.py
```

For a new machine, the bootstrap and package scripts under `setup` show installation steps, but paths and the ordinary Linux username must be adapted. Do not reinstall the GPU driver inside WSL; it uses the Windows driver. No registry adjustment is needed for ordinary inference or numerical CUDA tests.

## Interfaces and measurements

The agent produces exactly `{"tool":"tool_name","args":{...}}`. `GameBridge` validates the allowed arguments, converts prototype names, coordinates and entity handles, and rejects raw Python. Inventory is read-only; insertion is limited to supplied coal. Model text is never evaluated as Python.

`--context-policy history` retains conversation history and drops oldest complete action/feedback pairs at the token limit. `structured-memory` adds at most 512 tokenizer tokens of previously observed equipment and recent errors. Facts carry observation ticks and may be stale; no hidden-state lookups or extra model calls are used. Both conditions use greedy decoding, 8,192 total tokens, up to 1,024 output tokens and 32 decisions in the experiment script. The 30-minute wall budget is checked between decisions; it does not interrupt an in-flight operation.

The game pauses during inference. Movement temporarily advances at 10x for the pathfinder, with actual ticks logged. Successful ordinary actions add 60 ticks; waits advance exact requested ticks. Evaluation warms up for 60 simulated seconds and measures two windows of 3,600 ticks each. The target is 16 iron plates per window. Positive output remains unconfirmed success until a recorded supply-chain check rules out manual ore or crafting.

`steps.jsonl` records actions, observations, failures, response/environment latency, input/output token counts, history trimming, memory size and PyTorch peak allocated/reserved memory. GPU memory measurements exclude other processes. The scripted reference factory tests reachability and is never counted as model performance.

## C++ and CUDA operator

`rmsnorm_forward(input, weight, epsilon)` is a forward-only Python-callable C++ binding. Input must be contiguous BF16 CUDA data with last dimension 2,560; weight must be contiguous BF16 `[2560]` on the same device. Epsilon must be finite in `(0,1]`. Empty batches return an empty output. Unsupported shapes, types, gradients and CPU inputs raise errors. Compilation targets the host's compute capability 12.0 and uses no fast-math flag.

The kernel uses one 256-thread block per row, FP32 reduction, then BF16 rounding before weight multiplication and output rounding. It launches on PyTorch's current CUDA stream. The Python check compares captured real model tensors, zero/near-zero cases and random odd-row batches against installed Qwen RMSNorm and a float64 reference with BF16 rounding. A nondefault-stream case tests dispatch/dependencies.

Performance is measured on captured prompt `[1,1006,2560]` and token `[1,1,2560]` inputs already on the GPU. Both reference and custom functions allocate outputs. Three batches contain ten warm-ups per implementation and 100 alternating pairs. Report operator latency and its raw distribution separately from whole-model response speed; this pilot does not replace layers in Qwen.

On October 6, with explicit user permission, the reviewed RMSNorm suite passed memcheck, racecheck, initcheck and synccheck with zero reported errors; each ran all 25 correctness cases. The temporary Windows debugger-interface value was restored to its prior absent state. Evidence is in `evidence/artifacts/approved-sanitizer-validation.json`. This validates the bounded operator suite, not whole-model integration. GPU clocks, power and TDR settings were unchanged.

## Evidence

`evidence/runs` contains configurations, prompts, step logs, summaries and final states. `evidence/artifacts` contains versions, reference factory results, captured tensors, profiles and raw kernel measurements. `source-snapshots/context-pilot` preserves the evaluated agent implementation. Original signatures-only diagnostic runs are retained separately and must not be pooled with the corrected-interface comparison.

The report is `../outputs/Factorio Pilot Preliminary Report.md`. Longer runs, additional maps/models, recovery challenges and whole-model kernel integration belong to subsequent work.

## Guided working agent

`tools/working_agent.py` uses a smaller development tool set and an explicit factory procedure. It has completed two audited drill-to-furnace runs with eight model decisions, zero failed actions, and 19 plates in each measured minute. These guided results are separate from the frozen context experiment.

The runner defaults to **10× simulation speed and zero viewing delay**. It pauses the world while Qwen reasons. With the test server running, start a fast attempt from PowerShell:

```powershell
wsl -d Ubuntu-24.04 -u osci2 -- bash /mnt/c/Users/osci2/Documents/Codex/2026-10-05/igni/factorio-pilot/setup/run-working-agent.sh --visual --game-speed 10 --keep-visible-seconds 0
```

`--visual` uses the viewer-compatible tick advancement; it does not slow the default speed or require a viewer. Add `--require-viewer` only when joining before the run is required. Join a fresh server before FLE loads tools, because its runtime functions in game storage can still prevent later map saving and joins. Keep the private relay and server sessions alive while watching.

See `../outputs/Working Factorio Agent Results.md` for audited results, timing scope, source snapshots and packaging commands. The 49.16-second fast confirmation excludes model loading. Its exact simulation windows are unchanged.

## Source review and plate logistics

The user requires full C++/CUDA review before runtime testing. See `AGENTS.md` and `../outputs/CUDA and C++ Source Review.md`. GPU/model entry points check the exact reviewed native source hashes. A changed native file requires fresh inspection; custom benchmarking additionally requires matching bounded correctness results. The revised binding passed 25 correctness cases and all four bounded sanitizer checks after user authorization; the temporary setting was restored. The reviewed binding limits workloads to 8192 rows and rejects FP32 epsilon underflow/subnormal values and unresolved negative views. Original operator timing remains associated with the earlier source.

The opt-in `--logistics` mode provides `collect_output`, `place_storage` and `store_plates`, observed storage capacity, and an explicit carried-plate limit of 100. Transfers conserve real items and cannot insert ore/plates into furnace inputs. The scripted control demonstrates a full-output stall and recovery; it is excluded from model results.

```powershell
wsl -d Ubuntu-24.04 -u osci2 -- bash /mnt/c/Users/osci2/Documents/Codex/2026-10-05/igni/factorio-pilot/setup/run-working-agent.sh --logistics --target-plates-per-minute 32 --steps 32 --visual --game-speed 10 --keep-visible-seconds 0
```

The guided expansion run produced 38 and 37 plates per measured minute after adding a second chain in response to a rejected early completion request. It did not use storage tools. See `../outputs/Factorio Storage and Expansion Results.md` for the distinction, exact validation commands and the new source snapshot.

## Failure-oriented maintenance

`tools/maintenance_agent.py` gives a controller a prebuilt drill/furnace/chest, three coal per machine, and a verified 60-second warm-up. After that, EVERY decision advances exactly 15 simulated seconds, including invalid actions. There is no finish tool: two consecutive exact 60-second windows below 16 plates end the run as sustained failure. Otherwise it records survival through a 20-minute horizon or an incomplete wall-budget endpoint. Refills are limited to three coal per action; storage requires collection and transfer. These limits are disclosed benchmark rules.

For a checkout at a different path, the active maintenance launcher resolves its Python source relative to itself. Set `FACTORIO_PILOT_HOME` to the Linux directory containing `.venv`, `artifacts/starting-state.json`, and `runs`, then run `bash factorio-pilot/setup/run-maintenance.sh --controller idle --minutes 20` from the repository root. The pinned FLE installation and running server at `127.0.0.1:27000` are still required. Run controllers sequentially. The original host commands below remain the exact historical procedure and are not rewritten in saved configurations or source snapshots.

Run `--controller idle`, then `--controller scripted`, then `--controller model`, sequentially against the same server. All use the same frozen fixture and toolset. The model uses original PyTorch inference; integrating the reviewed C++/CUDA operator and measuring end-to-end acceleration are separate next steps. `../outputs/Factorio Maintenance Results.md` contains commands, audited results and limits. New maintenance sources and their configurations remain separate from the earlier construction experiment.
