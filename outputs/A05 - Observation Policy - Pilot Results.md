# A05 - Observation policy - Pilot results

Qwen failed after four game minutes with automatic statistics and after fifteen with requested inspection; it chose fourteen checks in the latter run. Both model episodes had zero failed tool actions. The scripted inspection controller survived twenty minutes.

This executed pilot checks whether Qwen requests current factory information when automatic updates are removed. It includes an inspection-paying scripted reachability control and one model episode per condition on one maintenance fixture. It is a machinery check, not a model ranking or a held-out policy evaluation.

## Methods

Both model conditions use the pinned Qwen3-4B-Instruct-2507 revision, original PyTorch BF16/SDPA inference, ordinary history, greedy decoding, 8,192 total tokens and 256 output tokens. The goal and game guide are identical. Each starts from the same saved reset state and scripted factory: one drill, furnace and chest, three coal per machine and a verified 60-second warm-up. Every decision, including check, failure and wait, advances 900 ticks (15 game seconds). Two consecutive 60-second windows below 16 plates end the episode. The horizon is 20 game minutes or 80 decisions, with a 600-second wall budget checked between decisions.

The automatic condition receives a fresh snapshot after each action. The requested condition receives an initial snapshot and refreshes only after a successful check, after that decision's 15-second advancement. Snapshot time and age are disclosed. Both receive the same filtered action feedback: success/failure, the tool name and a bounded transferred plate count where relevant. Nested raw results, inventory before/after counts and raw exception messages stay in the evaluator log. Production windows update in the prompt only when observation delivery permits them.

The scripted requested-inspection controller uses the visible snapshot and alternates maintenance with checking. Its success tests reachability under the inspection budget and is excluded from model scores. All five project native files were inspected, the exact-hash gate passed, and native sources remained unchanged. The custom RMSNorm backend, prefix reuse, memory policies and training were not varied in this experiment.

Both model runs used identical evaluated Python hashes, guide text and starting-state file hashes. Exact initial visible observation equality: **True**. The export audit replays visible state against the private trace and verifies retained source/export bytes. Thirty-six CPU tests passed, including six observation-policy tests covering leakage, stale timestamps, failed checks and copy isolation.

## Results

| Controller / observations | Endpoint | Game minutes | Decisions | Failed actions | Checks | Max snapshot age s | Input / output tokens | Episode wall s |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| scripted / requested | `survived_simulation_limit` | 20 | 80 | 0 | 40 | 15 | 0 / 0 | 166.72 |
| model / automatic | `sustained_production_failure` | 4 | 16 | 0 | 0 | 0 | 91136 / 321 | 54.53 |
| model / requested | `sustained_production_failure` | 15 | 60 | 0 | 14 | 60 | 407449 / 1052 | 226.42 |

Wall time excludes model loading and fixture setup. Response timing retains the A04 generation-only boundary, not K02's complete-response boundary; those timing tables must not be pooled. GPU memory is peak PyTorch allocation, not total device usage.

`A05-observation-requested-scripted-20261006T181451Z` plates by measured minute: `[18, 19, 19, 19, 18, 19, 19, 19, 18, 19, 19, 19, 18, 19, 19, 19, 18, 19, 19, 19]`. Peak allocated GPU bytes: `None`.

`A05-observation-automatic-model-20261006T182130Z` plates by measured minute: `[18, 19, 15, 5]`. Peak allocated GPU bytes: `9854640640`.

`A05-observation-requested-model-20261006T182355Z` plates by measured minute: `[18, 19, 19, 19, 18, 19, 19, 19, 18, 14, 18, 19, 18, 14, 9]`. Peak allocated GPU bytes: `9847599616`.

## Interpretation and limits

The requested controller did acquire information, but still missed timely furnace maintenance. After its last successful check (step 56), the snapshot used at step 57 showed zero stored furnace coal and 1,299,900 joules remaining in the burning piece. It next refueled the drill, collected and stored plates. The furnace had no fuel at the endpoint despite 447 coal remaining in reserve. This distinguishes gathering information from planning sufficient fuel margins; it does not prove that checking alone caused the longer episode. The automatic controller refilled the furnace with one coal at steps 3, 9 and 15, and its last two windows produced 15 and 5 plates.

This automatic-statistics condition is a new baseline with common filtered feedback, timestamps and observation guidance. It is not a byte-identical rerun of the earlier A04 ordinary-history episode; differences from A04 cannot be attributed to observation delivery alone.

These conditions change observation delivery, including the opportunity cost of inspection and resulting context length. They do not isolate reasoning ability from sensing cost or establish that longer history alone causes failure. A controller may infer changes from its own transfers; that is permitted information, not an automatic stat update. Previously observed state can legitimately be stale. Full evaluator observations and raw results remain private to the controller.

One episode per condition on one fixture cannot support a general improvement claim or a fine-tuning conclusion. Additional distinct frozen solvable fixtures and held-out tasks are still required. The scripted trace can seed examples, but it is not yet a training dataset or held-out benchmark. Any later fine-tuning comparison should retain this unchanged-model baseline and evaluate executed held-out episodes.

## Evidence and reproduction

[Visibility audit](../factorio-pilot/evidence/artifacts/A05-observation-audit.json) records replay checks and initial observations.

- [A05-observation-requested-scripted-20261006T181451Z](../factorio-pilot/evidence/runs/A05-observation-requested-scripted-20261006T181451Z/): configuration, fixture, action trace, summary, exact source snapshots and export hashes.

- [A05-observation-automatic-model-20261006T182130Z](../factorio-pilot/evidence/runs/A05-observation-automatic-model-20261006T182130Z/): configuration, fixture, action trace, summary, exact source snapshots and export hashes.

- [A05-observation-requested-model-20261006T182355Z](../factorio-pilot/evidence/runs/A05-observation-requested-model-20261006T182355Z/): configuration, fixture, action trace, summary, exact source snapshots and export hashes.

From the repository root in the configured ordinary-user Linux runtime:

```bash
export FACTORIO_PILOT_HOME="${FACTORIO_PILOT_HOME:-$HOME/factorio-pilot}"
sudo docker compose -f "$FACTORIO_PILOT_HOME/cluster/compose.yaml" start factorio_0
"$FACTORIO_PILOT_HOME/.venv/bin/python" factorio-pilot/tools/maintenance_agent.py --controller scripted --observation-policy requested --minutes 20
sudo docker compose -f "$FACTORIO_PILOT_HOME/cluster/compose.yaml" start factorio_0
"$FACTORIO_PILOT_HOME/.venv/bin/python" factorio-pilot/tools/maintenance_agent.py --controller model --observation-policy automatic --minutes 20
sudo docker compose -f "$FACTORIO_PILOT_HOME/cluster/compose.yaml" start factorio_0
"$FACTORIO_PILOT_HOME/.venv/bin/python" factorio-pilot/tools/maintenance_agent.py --controller model --observation-policy requested --minutes 20
```

Run sequentially against the existing local server: each command resets the world. Review every native file and confirm the exact-hash gate before GPU/model runs. The pinned FLE environment, model snapshot and reset artifact are external runtime prerequisites described in the [runtime README](../factorio-pilot/README.md). The default observation policy remains legacy A04; explicit automatic/requested modes create A05 records.

An earlier automatic attempt, `A05-observation-automatic-model-20261006T181856Z`, stopped at RCON connection before gameplay because the server was not running. It is excluded from scores. The server log recorded SIGTERM after the preceding control; the SIGTERM source was not established. Restarting the existing container before the next model attempt allowed it to connect. This is an infrastructure failure, not a model maintenance failure.
