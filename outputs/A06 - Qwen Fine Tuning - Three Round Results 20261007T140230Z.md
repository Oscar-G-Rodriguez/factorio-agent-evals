# A06 Qwen fine tuning: three-round results

Workflow `A06-three-round-20261007T140230Z`. Recorded phase: **incomplete**; completed training rounds: **2/3**.

## Current outcome

The experiment stopped after two actual training rounds. All five round-two correction proposals passed exact-state replay and the original 20-minute continuation, but the frozen protocol requires at least eight distinct verified corrections before round three. Recomputing the rule on all 320 round-two training decisions found exactly five eligible states; the four-per-factory cap discarded none. Round three and all 15 final-test episodes remain unperformed.

The selected round-two adapter produced 746 new plates across the two validation factories, compared with 680 for unchanged 4-bit Qwen: 66 additional plates, or 9.7%. Failed actions fell from eight to zero. Both conditions reached the 20-minute cap on both factories, so there was no measured survival increase. These are validation results used for checkpoint selection, not a final-test or generalization claim. Both round-two checkpoints tied on survival and plates; update 20 won the frozen earliest-checkpoint tiebreaker.

Round one regressed on validation and remains part of the evidence. Round two then continued its selected adapter using a fresh optimizer and a mixture of 160 original examples and 160 samples from 13 distinct verified round-one corrections. The round-two training factories all survived their capped horizon, but those factories contributed training data and cannot establish held-out improvement.

## Methods

Single-seed QLoRA on Qwen3-4B-Instruct-2507. Original four train, two validation and three test fixtures share one factory layout. The guide, automatic observations, two history pairs, greedy decoding and 15-second simulation cadence are held fixed. Adapters are trained separately from gameplay; base weights remain frozen. Each round selects update 20 or 40 using validation survival, plates and earliest checkpoint. Corrections require train-only execution from exact native pre-action state and successful continuation through the original horizon. No custom RMSNorm is used in this comparison.

## Results

| Purpose | Condition | Update | Factory | Survival (s) | New plates | Failed actions | Endpoint |
| --- | --- | ---: | --- | ---: | ---: | ---: | --- |
| train-diagnostic | round1_4bit | 40 | train_carry | 120 | 10 | 1 | sustained_production_failure |
| train-diagnostic | round2_4bit | 20 | train_carry | 1200 | 373 | 0 | survived_simulation_limit |
| train-diagnostic | unchanged_4bit | — | train_carry | 120 | 10 | 0 | sustained_production_failure |
| train-diagnostic | round1_4bit | 40 | train_drill | 360 | 80 | 0 | sustained_production_failure |
| train-diagnostic | round2_4bit | 20 | train_drill | 1200 | 374 | 1 | survived_simulation_limit |
| train-diagnostic | unchanged_4bit | — | train_drill | 360 | 80 | 0 | sustained_production_failure |
| train-diagnostic | round1_4bit | 40 | train_furnace | 360 | 80 | 0 | sustained_production_failure |
| train-diagnostic | round2_4bit | 20 | train_furnace | 1200 | 375 | 0 | survived_simulation_limit |
| train-diagnostic | unchanged_4bit | — | train_furnace | 1140 | 312 | 1 | sustained_production_failure |
| train-diagnostic | round1_4bit | 40 | train_output | 120 | 10 | 1 | sustained_production_failure |
| train-diagnostic | round2_4bit | 20 | train_output | 1200 | 375 | 1 | survived_simulation_limit |
| train-diagnostic | unchanged_4bit | — | train_output | 540 | 149 | 4 | sustained_production_failure |
| validation | round1_4bit | 20 | validation_fuel | 120 | 10 | 0 | sustained_production_failure |
| validation | round1_4bit | 40 | validation_fuel | 300 | 70 | 0 | sustained_production_failure |
| validation | round2_4bit | 20 | validation_fuel | 1200 | 371 | 0 | survived_simulation_limit |
| validation | round2_4bit | 40 | validation_fuel | 1200 | 371 | 1 | survived_simulation_limit |
| validation | unchanged_4bit | — | validation_fuel | 1200 | 327 | 7 | survived_simulation_limit |
| validation | round1_4bit | 20 | validation_storage | 120 | 5 | 1 | sustained_production_failure |
| validation | round1_4bit | 40 | validation_storage | 120 | 5 | 0 | sustained_production_failure |
| validation | round2_4bit | 20 | validation_storage | 1200 | 375 | 0 | survived_simulation_limit |
| validation | round2_4bit | 40 | validation_storage | 1200 | 375 | 1 | survived_simulation_limit |
| validation | unchanged_4bit | — | validation_storage | 1200 | 353 | 1 | survived_simulation_limit |

Full token, latency and GPU-memory measurements are in `comparison.csv`; target-token losses are in `training-curves.csv` when training completed.

## Timing and training measurements

| Condition | Validation factory | Median first token (s) | Median remaining generation (s) | Median game advancement (s) |
|---|---|---:|---:|---:|
| round1_4bit | validation_fuel | 0.3123 | 0.6043 | 1.7718 |
| round2_4bit | validation_fuel | 0.3384 | 0.6922 | 1.8441 |
| unchanged_4bit | validation_fuel | 0.2333 | 0.7350 | 1.6917 |
| round1_4bit | validation_storage | 0.3029 | 0.6085 | 1.8691 |
| round2_4bit | validation_storage | 0.3365 | 0.6975 | 1.8750 |
| unchanged_4bit | validation_storage | 0.2383 | 0.7745 | 1.7384 |

Each interval is recorded separately in the action traces; `phase-timing-summary.json` retains context preparation, first-token, remaining generation, tool execution, game advancement, and full response aggregates for every episode. Different actions, output lengths, and episode horizons prevent interpreting these measurements as a matched inference speed benchmark. First-token timing includes prompt processing. Gameplay time pauses during inference.

| Training round | Updates | Duration (min) | Peak allocated (GiB) | Peak reserved (GiB) | Mean target-token loss |
|---|---:|---:|---:|---:|---:|
| 1 | 40 | 11.05 | 8.09 | 8.53 | 0.145926 |
| 2 | 40 | 10.96 | 8.09 | 8.53 | 0.036963 |

Round-two loss uses a different data mixture, so losses across rounds are not directly comparable. Neither loss alone nor the many heuristic waiting flags on successful episodes establishes gameplay improvement or the cause of waiting.

## Failures and limitations

Corrective release did not meet verified-data gate; stop incomplete.

Survival is capped at 1,200 simulated seconds. Wall-time cutoffs are incomplete observations, not game failures. Waiting-opportunity flags are heuristics, not causal proof. First-token latency includes prompt processing and first-token generation. The three reserved test factories were never opened by this workflow. One seed, two validation factories used for selection, and shared factory geometry do not establish broad generalization or statistical significance. Validation-selected checkpoints and training losses cannot substitute for final test results.

## My contribution

Built the constrained JSON game adapter, visible-context boundary, fixture and failure evaluation, supervised-data verification, QLoRA workflow, native-state correction replays, checkpoint selection and analysis. FLE supplies the game connection; Qwen supplies pretrained weights; PyTorch, PEFT and bitsandbytes supply training primitives. The separate project-authored C++/CUDA RMSNorm experiment retains its own correctness and inference timing evidence.

## Resume evidence

- Implemented an audited local QLoRA and Factorio evaluation pipeline; completed 2 training rounds and 22 logged model episodes in this workflow.
- Trained two sequential QLoRA adapters for a local Qwen3-4B Factorio maintenance agent; on two validation factories, the selected second-round adapter produced 746 versus 680 plates (+9.7%) with zero versus eight failed actions. Final-test evaluation remains unperformed.
- Built train-only correction verification using exact saved game states and full-horizon continuation, retaining 21 replay outcomes and stopping the planned third round when only five of eight required corrective examples were available.

## Reproduction

The recorded host uses Ubuntu 24.04 under WSL2, Python 3.12.3, an RTX 5070 Ti, PyTorch 2.11.0+cu128, Transformers 4.57.6, Accelerate 1.15.0, PEFT 0.18.1, bitsandbytes 0.50.2, and Matplotlib 3.11.2. Qwen/Qwen3-4B-Instruct-2507 is pinned to revision `cdbee75f17c01a7cc42f958dc650907174af0554`.

The exact environment and full package inventory are retained in the exported preflight run's `environment.json` and `environment-freeze.txt`. The training environment inherits read-only inference dependencies through an explicit `.pth` pointing at the original environment; PEFT and bitsandbytes were installed separately with `--no-deps`. Recreating that environment requires its pinned base dependencies, not simply installing the two added packages.

From the public checkout, these CPU-only checks inspect existing evidence without launching a model:

```bash
python scripts/verify_a06_protocol.py
python scripts/verify_a06_three_round_evidence.py
python scripts/verify_maintenance_evidence.py
cd factorio-pilot/tools
/home/osci2/factorio-pilot/.venv-a06-train/bin/python -m unittest test_a06_workflow test_a06_execution test_a06_context test_a06_fixture_controls
```

The original full-workflow launch is recorded below for reproduction, not as a command to resume the data-gate failure:

```bash
sudo /home/osci2/factorio-pilot/.venv-a06-train/bin/python \
  factorio-pilot/tools/a06_orchestrate.py \
  --runtime-home /home/osci2/factorio-pilot --owner osci2 \
  --preflight-run /home/osci2/factorio-pilot/runs/A06-training-preflight-three-round-20261007T1350
```

It requires the external FLE installation, licensed Factorio 2.0.73 server and Docker setup, pinned local model snapshot, verified native fixture archives, runtime artifacts, and reviewed native sources. The preflight must match the current source and protocol hashes. Fixture paths and hashes are recorded in the frozen protocol and workflow receipts; cloning alone does not recreate these external resources. Read the runtime README, fixture-control reports, and native source review before any GPU execution. Model weights, adapters, optimizer tensors, native game archives, and executables remain outside Git with hash receipts inside it.

Packaging existing terminal evidence is CPU-only. The package has already been created and its exporter deliberately refuses to overwrite it:

```bash
/home/osci2/factorio-pilot/.venv-a06-train/bin/python factorio-pilot/tools/a06_package.py \
  --runtime-home /home/osci2/factorio-pilot \
  --workflow /home/osci2/factorio-pilot/workflows/A06-three-round-20261007T140230Z
```

Report edits and the explicitly labeled insufficient correction dataset were added after the generic export; the final manifest records their hashes. Reproduce their interpretation from the raw traces and correction receipts rather than treating the exporter as the complete analysis.

## Correction gate evidence

[Frozen candidate-rule audit](../factorio-pilot/evidence/artifacts/A06-round2-candidate-rule-audit.json) records all four training traces and the five eligible states. The partial correction dataset is preserved under the experiment's `insufficient-corrections-round2/` directory with `accepted_for_training: false`. Its examples passed replay verification but the set failed the minimum-count gate. It must not be used to silently resume the unchanged three-round protocol.

Completing three rounds requires an explicitly revised protocol that obtains additional distinct training situations or changes the data requirement. The existing final-test factories must remain reserved. This report preserves the authorized incomplete outcome; it does not fulfill the three-round finish line.
