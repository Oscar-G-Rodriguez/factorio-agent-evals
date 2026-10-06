# Qwen maintenance fine tuning protocol

Protocol version `a06-qwen-sft-v1`, dated October 6, 2026. The experiment asks whether supervised fine-tuning improves Qwen's fuel and storage decisions on reserved combinations of factory conditions. It uses the existing maintenance tools and a common compact prompt. The protocol and split are fixed before data collection; fixture preparation, controls, dataset construction and training are subsequent work.

The [machine-readable contract](../factorio-pilot/protocols/a06-qwen-sft-v1.json) owns numerical settings and fixture membership. The [common game guide](../factorio-pilot/protocols/a06-game-guide.txt) owns the system message. Changes to either require a new protocol version, retained previous bytes and fresh controls. This stage freezes recipes, not validated game saves: no new fixture has yet demonstrated reachability.

## Task and outcome

One burner mining drill supplies ore directly to one stone furnace. A wooden chest receives plates only when the agent stores them. The actor is within transfer range of all three entities. Construction, expansion, movement and steel production are outside this experiment.

Setup resets the recorded [starting state](../factorio-pilot/evidence/artifacts/starting-state.json), constructs the chain through the existing tools, and verifies a 60-second warm-up with at least 16 newly produced plates. While paused, fixture preparation then sets the declared coal, burning energy and plate inventories. These are disclosed starting endowments, not model actions or rewards. Existing burning fuel must be coal and its remaining energy must be within one coal's capacity; preparation must read back every preset and save the complete paused state. The evaluator then establishes a fresh tick and production-counter origin. Preloaded plates, setup and warm-up production do not contribute to the measured rate.

Coal contains [4 MJ per piece](https://wiki.factorio.com/Coal). The current [LuaBurner API](https://lua-api.factorio.com/latest/classes/LuaBurner.html) permits setting the burning item and remaining energy, with the item established first. These latest API docs are not validation of the pinned Factorio 2.0.73 runtime: Stage 2 must verify setters and exact saved-state restoration there before accepting a fixture.

Every decision advances exactly 900 ticks, including check, wait, malformed output and rejected game actions. The world pauses during inference. Each nonoverlapping 3,600-tick window must produce at least 16 new iron plates. Two consecutive low windows terminate the episode; an adequate window resets the streak. A passing window alone never ends evaluation. The horizon is 1,200 game seconds or 80 decisions. A 600-second wall budget, checked between decisions, produces an incomplete budget endpoint rather than a game failure. Record an in-flight timeout separately; never reset and relabel an interrupted episode as a normal failure.

This is supervised learning. There is no scalar gameplay reward in the training objective. Gameplay outcomes evaluate the trained model; supervised loss trains it to produce reviewed action tokens.

## Fixtures and partitions

All fixtures share the same map, geometry, capacities and cadence. Counts below are exact post-warm-up presets. Remaining burning energy is shown in megajoules; the JSON stores joules. Stored coal and the piece already burning are separate observations.

| Fixture | Partition | Drill coal / MJ | Furnace coal / MJ | Output plates | Carried plates | Chest plates | Reserve coal |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| train_drill | Train | 0 / 1 | 3 / 3 | 20 | 0 | 0 | 400 |
| train_furnace | Train | 3 / 3 | 0 / 1 | 20 | 0 | 0 | 400 |
| train_output | Train | 3 / 3 | 3 / 3 | 90 | 0 | 0 | 400 |
| train_carry | Train | 3 / 3 | 3 / 3 | 90 | 100 | 0 | 400 |
| validation_fuel | Validation | 0 / 3 | 0 / 3 | 30 | 0 | 200 | 300 |
| validation_storage | Validation | 2 / 3 | 2 / 3 | 95 | 100 | 400 | 300 |
| test_drill_storage | Test | 0 / 3 | 1 / 1.5 | 85 | 100 | 600 | 200 |
| test_furnace_output | Test | 2 / 3 | 0 / 2 | 98 | 40 | 800 | 200 |
| test_reserve_storage | Test | 1 / 2 | 1 / 2 | 75 | 60 | 1100 | 100 |

The split tests new combinations and starting inventories on one map. It does not establish generalization to unseen maps, factory layouts, construction or broader Factorio play. The smaller test reserve is intended to remain sufficient through the horizon; only executed scripted controls can establish that claim.

Before examples or model comparisons are collected, every fixture must pass an executed scripted 20-minute control under the same tools, transfer limits and cadence. Record idle controls as well; they need not fail at the same minute. Log inventory conservation, actual starting state, all production windows and ore delivery. Compare observed presets exactly, with absolute tolerance of one joule for burning energy; refuse a mismatched save. These checks must produce hashed fixture snapshots and a control manifest. If a fixture proves unsolvable or its preparation unsupported, revise the protocol before training. Never silently adjust an evaluation fixture after seeing model outcomes.

Train episodes may supply optimization examples. Validation episodes may select checkpoints and training settings, but never supply optimizer examples. Test episodes may supply only reachability-control evidence and the final locked model evaluation. Their scripted actions, corrections, state replays and failures must not become examples, retrieval content, prompt hints or checkpoint-selection input. Test controls establish environmental validity, not policy performance. Human designers already know these planned recipes; held out means excluded from learning and model selection, not secret from the researcher.

Split by fixture and source episode before extracting decisions. Reserve every replay and descendant of an episode in that episode's partition. Reject exact duplicate serialized model inputs across partitions. Different handles, timestamps or metadata do not make the same state a different example: check semantic duplicates after excluding handles, absolute tick origin and provenance IDs. Also review near duplicates and overlapping episode segments. Do not split adjacent steps randomly.

## Information available to Qwen

Version 1 uses automatic observations, with no retrieval, structured-memory policy, custom kernel, cross-decision prefix cache or prompt improvement varied during the adapter comparison. This isolates training within the new input contract. Requested inspection and alternative context policies need separate protocols.

Each user message contains a whitelist projection of `ObservationPolicy.visible`: observation policy; relative elapsed and observation ticks; snapshot age; inventory coal and carried plates; carrying count, available space and 100-plate limit; and observed equipment. Each entity includes its current handle, name, position and status. Burner entities include stored coal and remaining burning joules. Furnace and chest include plate count and free plate capacity. Include the last two measured production windows and filtered feedback from the previous action, using the A05 allowlist. Equipment is sorted by name and position; numeric values remain observations, not predictions. Omit duplicate prose inventories, raw nested tool results, raw exception text and opaque FLE warnings.

The current automatic snapshot has age zero. The same fixed game guide and tool syntax appear in all conditions. The model receives at most two previous executed decision pairs, oldest first: their user payload and the action actually attempted. A teacher correction must not replace the action that was really executed in history. Feedback belongs in the following user payload. Use canonical UTF-8 JSON with sorted keys, compact separators and finite numbers; the builder must reject unknown model-visible fields rather than silently include evaluator metadata.

The message sequence is one system message, zero to two historical user/assistant pairs, and the current user message. Qwen's pinned tokenizer and chat template then serialize it. The total inference budget is 4,096 tokens, including 256 reserved generated tokens; prompt size is at most 3,840 tokens. If needed, remove the oldest complete historical pair until the prompt fits. Never truncate the guide, current snapshot, tool syntax or target action. Oversized essential inputs are rejected and logged. The same renderer and trimming rule must build training inputs and evaluation prompts.

This compact format differs from A04/A05 history and their 8,192-token budgets. Run fresh unchanged-model baselines; historical scores are context, not matched controls. The future memory-fit probe must support this contract or create a documented new version before collection rather than silently shorten context.

No final outcome, future state, teacher rationale, correct-action hint, fixture ID, partition, source run ID, checkpoint ID or private monitor field belongs in a model message. Actual observed production windows are allowed; unseen evaluator annotations are not.

## Actions and training examples

Qwen outputs exactly one JSON object with `tool` and `args`. The action space is unchanged: fuel an observed drill or furnace with an integer 1 to 3 coal; collect 1 to 100 plates from the observed furnace; store 1 to 100 plates in the observed chest; check with empty arguments; or wait with empty arguments. No finish action exists. Resolve handles from the current observation and validate through `MaintenanceBridge.action`. Do not mask choices, insert actions or repair a model's output during scored episodes.

Each JSONL example has these fields:

| Field | Required content |
| --- | --- |
| `schema_version` | Integer 1. |
| `protocol_id` | `a06-qwen-sft-v1`. |
| `fixture_id`, `partition`, `episode_id`, `decision_index` | Provenance outside the messages. Partition comes from the fixture registry, never from a row's assertion alone. |
| `messages` | The exact rendered input sequence defined above, excluding the target assistant message. |
| `target_action` | One validated action object. Serialize canonically as the final assistant message for training. |
| `label_source` | `executed_scripted` or `reviewed_replay`. |
| `evidence` | Source trace and decision hashes; snapshot hash; teacher action execution receipt; continuation run ID and endpoint; reviewer record for corrections. |
| `input_sha256` | Hash of canonical pre-template messages. Also store tokenizer revision and token counts in the dataset manifest. |

A scripted label is eligible only when that action was executed successfully from the recorded visible state and the scripted episode survived the full horizon. A correction to a failed Qwen decision is only a candidate until replayed from the exact pre-action save, successfully executed, and continued by the scripted controller through the original horizon. Replay history must still describe what occurred before the corrected decision. Local success alone does not prove that a label supports sustained production. Discard unavoidable or unverified states and document exclusions.

Training applies cross-entropy loss only to target assistant action tokens and the template's corresponding end token. System, user, historical assistant and padding tokens are masked from loss. Labels can have several valid alternatives; teacher imitation does not establish a globally optimal policy. Preserve the choice and its evidence rather than inventing a unique correct answer.

Begin with executed scripted train episodes and targeted verified corrections from train fixtures. Historical A05 scripted steps can inform teacher design but do not become version 1 rows without recollection or exact verified replay using the new fixtures and input renderer. Teacher rationales may be retained for review outside model inputs; version 1 targets contain JSON actions only.

A dataset release must record row counts by partition and behavior, all excluded rows and reasons, episode membership, semantic-duplicate checks, source and file hashes, token-length distributions and the common guide hash. Check low drill fuel, low furnace fuel, near-full output, full carrying inventory and competing needs. A script must reject validation/test rows at the optimizer-data boundary. Training runs reference an immutable dataset release; never overwrite one after training begins. Quantity targets and training hyperparameters are selected after collection and the memory probe, not invented before trustworthy examples exist.

## Matched model comparisons

Use `Qwen/Qwen3-4B-Instruct-2507`, revision `cdbee75f17c01a7cc42f958dc650907174af0554`, with the same tokenizer. The primary pair is unchanged 4-bit Qwen versus the same 4-bit base plus the learned LoRA adapter. This controls for quantization. Add an unchanged BF16 baseline to expose quantization differences. Freeze the original PyTorch normalization path, SDPA attention where supported, greedy decoding, EOS/complete-object stopping, prompt renderer and fixture snapshots. Do not upgrade the historical inference runtime in place; freeze the training dependencies after the compatibility probe in a separate declared environment.

Run validation fixtures during development. Select the checkpoint by greatest mean restricted survival through 1,200 seconds on the two validation fixtures; break ties by measured newly produced plates, then earliest checkpoint. Any wall-budget endpoint leaves that comparison incomplete and cannot win selection until resolved. Lock the dataset, prompt, training configuration and selected checkpoint before model inference on test fixtures. A prompt-improved baseline, if added later, must be developed solely on train/validation and locked before testing.

For the first smoke comparison, use one training seed, 42, with one greedy episode per each of the three distinct test fixtures and each baseline. This is a bounded pilot. Repeating identical greedy episodes is a repeatability check, not additional independent task evidence. Broader improvement claims require separately trained seeds 43 and 44 and the same evaluation fixtures; report per-fixture results and variability across trained adapters. After test results have been inspected, further tuning makes this test set development data and requires a new reserved test set for another final claim.

Measure restricted survival and endpoint, every minute's newly produced plates, failed actions per attempted action, repeated failures, inspections, token counts, complete response latency and episode wall time. Latency starts before rendering/tokenization and ends after JSON parsing/validation, before game execution; log generation time separately. Report median and p95 only with sample counts. Record loading/setup separately, GPU peak allocated and reserved memory, and total device usage separately if sampled. Compare tool errors with infrastructure failures; do not count a lost server connection as a model decision failure.

Custom RMSNorm inference on the trained model is a later K experiment, following full native review, matching numerical evidence and behavioral validation. The existing forward-only kernel is excluded from training. No training speedup or improvement is inferred from K01/K02 timings.

## Stage completion and next work

Stage 1 is complete when the protocol, common guide and disjoint fixture recipes are saved, numerical settings agree, their hashes are recorded, and navigation identifies them as the next experiment. It does not require data collection, new game saves or GPU execution. The recipe checker is CPU-only and is not a reachability or dataset audit.

Before Stage 2, implement deterministic fixture preparation and the common renderer, validate all nine scripted and idle controls, then retain byte-hashed snapshots. Build and audit examples only afterward. Before Stage 3, fully inspect every project-authored C++/CUDA source and pass the existing exact-hash gate; never regenerate approval to bypass inspection. Trainable adapter weights, base weights, environments and game binaries remain outside Git. Reports and run folders use stage A06 and link exact source, protocol, dataset and model hashes.
