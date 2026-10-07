# A06 Qwen fine tuning three round protocol

This experiment trains three successive QLoRA adapters for the existing Factorio maintenance task. Each round is followed by executed validation; rounds one and two also produce train-only corrective examples for the next round. The final comparison opens the three test factories only after all adapter and source choices are locked.

The machine-readable contract is [a06-three-round-v1.json](../factorio-pilot/protocols/a06-three-round-v1.json). Earlier protocols, 320-example dataset releases, compatibility probes and interrupted attempts remain separate. They do not count as completed training rounds.

## Sequence and decisions

Run unchanged 4-bit Qwen on four training and two validation fixtures. Train round one on all 320 audited examples. Evaluate updates 20 and 40 on both validation fixtures, choosing mean capped survival, total new plates and then earliest update. The chosen adapter is attached alone during gameplay.

For rounds two and three, continue the preceding selected adapter with a fresh optimizer. Mix 160 original rows with 160 sampled verified corrections from the immediately preceding round. Require eight distinct corrective examples across two train fixtures; inspect no more than four candidates per fixture. A target proposal alone is insufficient: reproduce the model prefix, save and restore the exact pre-action native state, execute the correction, verify the observed problem changes and continue through the original horizon without sustained failure. Preserve actual model history. Insufficient data ends the experiment incomplete.

Keep all three selected adapters, including worse rounds. After locking their hashes and evaluation sources, run unchanged BF16, unchanged 4-bit and each trained adapter on three reserved test fixtures: 15 final episodes. The main comparison controls quantization by using the 4-bit base. Training and checkpoint selection never consume final test observations.

## Training and measurements

Use pinned Qwen3-4B-Instruct-2507, NF4 double quantization, BF16 compute, rank 8, alpha 16, dropout zero and all-linear adapter targets. Seed 42; learning rate 0.0002; 40 optimizer updates with eight batch-one examples per update. Train only target assistant action and end-token labels. Reject sequences above 2,048 tokens without truncation. Release unused cached GPU allocations after each example, preserving the separate runtime-memory probe.

Save resumable adapter, optimizer and RNG state every five updates; updates 20 and 40 are the only selection candidates. The custom forward-only RMSNorm is excluded. Native review and source-hash gates apply before every GPU entry point.

Use current observations, two history pairs, greedy generation and a fixed 15-second simulation cadence. Inference pauses simulation. End at two consecutive one-minute windows below 16 new plates or the 20-minute horizon; a ten-minute wall cutoff is incomplete. Measure survival, new plates, failed actions, waiting opportunities, tokens, first-token and remaining-generation time, tool time, simulation time and GPU memory. First-token time includes prompt processing. Waiting flags are diagnostic heuristics, not causal findings.

## Execution and recovery

The workflow has one GPU worker and one game controller, a 12-hour total cap and one infrastructure retry per stage. Completed gameplay failures are retained rather than retried for a better score. Check process ID, start time and command before classifying a worker. A user pause stops subsequent jobs and saves training state at the next optimizer boundary.

Regular chat updates are requested every 15 minutes and at stage changes. Scheduling belongs to the existing Codex automation; durable notes hold the protocol and evidence links. Keep model weights, adapters, optimizer tensors and native maps outside Git.

## Reproduction

Run from the public checkout; root is used only for Docker orchestration and model workers run as the ordinary runtime owner:

```bash
export FACTORIO_PILOT_HOME=/home/osci2/factorio-pilot
"$FACTORIO_PILOT_HOME/.venv-a06-train/bin/python" -m unittest discover -s factorio-pilot/tools -p 'test_*.py'
sudo "$FACTORIO_PILOT_HOME/.venv-a06-train/bin/python" -u factorio-pilot/tools/a06_orchestrate.py --runtime-home "$FACTORIO_PILOT_HOME" --owner osci2
```

The training environment preserves the existing inference environment. It adds `peft==0.18.1` and `bitsandbytes==0.50.2` without upgrading inherited `torch==2.11.0+cu128`, `transformers==4.57.6` and `accelerate==1.15.0`; `pip check` must pass. Environment inventory, package locations, model revision, source snapshots and exact launch arguments are captured in evidence. A full installed-package inventory includes OS packages and is forensic evidence, not an instruction to reinstall every package with pip.

For a recorded safe-boundary pause, resume the same unchanged workflow with `--resume-workflow <external-workflow-directory>` after explicitly clearing its pause request. The source and protocol checks reject incompatible continuation. Native fixture archives are immutable masters; restored servers receive disposable copies.

## Interpretation

This is a single-seed, same-layout maintenance pilot. Training loss is not gameplay improvement. Capped survival is not indefinite reliability. Three related test fixtures do not establish broad Factorio competence or statistical significance. Resume claims must name the executed task, measured comparison and sample count. Existing K01/K02 kernel results retain their own measurement scope.
