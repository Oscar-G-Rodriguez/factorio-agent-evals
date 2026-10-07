# Qwen maintenance training dataset audit

The common A06 context renderer and an immutable, training-only dataset are complete. The final release contains **320 successfully executed scripted decisions from four training fixtures**, with execution receipts and surviving 20-minute continuations. Its CPU audit reconstructs every example from the original traces. This provides supervised examples for the next QLoRA compatibility and memory probe; it does not establish that Qwen has learned or improved.

## Examples and provenance

Each training fixture contributes 80 decisions. The unchanged teacher maintained production for the full horizon with 375 new plates and no failed actions per episode. See the [fixture suite](A06%20-%20Qwen%20Fine%20Tuning%20-%20Fixture%20Suite%20Results.md) for reachability and save restoration evidence. The builder reads only the four train traces, never validation/test scripted actions or the test-only congestion replay.

Inputs were rendered offline from the fully recorded pre-action observations and actual previous actions. These are labels from executed gameplay, rather than new model episodes or unevaluated proposals. Each row retains its fixture/episode lineage, decision and trace hashes, fixture snapshot hash, execution receipt hash and full-horizon continuation endpoint outside the model messages.

| Label behavior | Rows |
| --- | ---: |
| Refill drill | 61 |
| Refill furnace | 37 |
| Collect plates | 25 |
| Store plates | 25 |
| Wait | 172 |
| Total | 320 |

There are no check labels or reviewed-replay corrections in this release. All 320 candidates were eligible; no rows were excluded, history-trimmed or downsampled. Waits are 53.75% of the labels. This is a small, imbalanced teacher-imitation dataset; unnecessary waiting and missed storage/fuel actions deserve separate attention in subsequent model evaluations. The labels do not claim a unique optimal action.

## Common context and loss

[`a06_context.py`](../factorio-pilot/tools/a06_context.py) implements the shared training/inference rendering function. It uses the frozen game guide and tool syntax, automatic observed facts, filtered previous-action feedback and the last two completed production windows. Time is relative to the episode origin. Equipment is sorted by name and position. Raw production counters, duplicate inventory prose, opaque warnings, private identifiers, teacher hints and evaluator low-window annotations are excluded. Production windows expose only their index, relative start/end ticks, duration and newly produced plate count. Unknown fields, nonfinite numbers, inconsistent capacities and future observations are rejected.

The renderer retains at most two historical user/assistant pairs, using the action actually attempted. It checks chronology and removes only the oldest whole pair when necessary. Oversized essential inputs are rejected rather than truncated. A future A06 live controller must call this same function; historical A04/A05 controllers retain their original prompts and budgets.

Qwen's pinned tokenizer and chat template serialize the messages. The loss mask covers only the target action JSON and its assistant end token. System/user messages, historical assistant actions, assistant headers and padding are masked. Actual tokenizer checks verified all 320 targets and 628 historical assistant messages, including target round trips and padding masks.

| Token measurement | Minimum | Median | p95 | Maximum |
| --- | ---: | ---: | ---: | ---: |
| Prompt | 802 | 1676 | 1713 | 1723 |
| Target including end token | 10 | 10 | 24 | 24 |
| Training sequence | 821 | 1690 | 1730 | 1741 |

The frozen limits remain 3,840 prompt tokens, 256 generated tokens and 4,096 total tokens. Tokenization used Transformers **4.57.6** and Qwen revision `cdbee75f17c01a7cc42f958dc650907174af0554`. Tokenizer file hashes are retained in the manifest. These token counts do not establish GPU training memory fit.

## Dataset audit

The [final release manifest](../factorio-pilot/evidence/datasets/A06-scripted-train-v1-20261007-r3/manifest.json) records source/file hashes, membership, counts and token distributions. The [audit receipt](../factorio-pilot/evidence/artifacts/A06-dataset-audit-r3.json) verifies exact reconstruction, successful execution, full-horizon continuation, budgets and target-only loss. All five reserved fixtures were rejected even when a test row falsely asserted `partition: train`. The training ingress, `load_optimizer_dataset`, audits the release before returning encoded examples.

There were zero exact input duplicates and zero semantic duplicates after replacing handles with stable entity name/position references. A broader screen found no identical current physical observations. Across 38,400 pairs from different training fixtures, no pairs met the numerical near-state threshold: matching geometry/status and maximum normalized physical-coordinate difference at most 0.05. The [duplicate audit](../factorio-pilot/evidence/datasets/A06-scripted-train-v1-20261007-r3/duplicate-audit.json) defines the normalizers. This tight screen does not establish independence: all episodes share one layout, deterministic teacher and closely related maintenance patterns. Adjacent decisions remain correlated; their episode lineages stay in train.

Validation and test contain **zero optimizer examples**. Their future model episodes remain reserved for selection and final evaluation. Semantic cross-partition input checks must also run when evaluation prompts are collected; this release does not claim to compare against uncollected evaluation prompts.

Two earlier builds are preserved as superseded candidates: `A06-scripted-train-v1-20261007` and its `-r2` revision. The first predates strengthened chronology/similarity checks. The r2 execution/token audit passed under its source, but final boundary review found derived evaluator annotations in production windows. The r3 renderer removes those annotations and retains only observed window measurements; a fresh release and audit preserve that correction. Use **r3** for training. Candidate directories and their receipts remain unchanged; changed code or examples require a fresh release.

## Reproduction

From the repository root, use the existing pinned environment and locally cached tokenizer. No game server, model weights in memory or GPU execution is required. Set `TOKENIZER_SNAPSHOT` to the local directory named by the pinned revision above.

```bash
"$FACTORIO_PILOT_HOME/.venv/bin/python" scripts/verify_a06_dataset.py \
  --tokenizer-snapshot "$TOKENIZER_SNAPSHOT"
"$FACTORIO_PILOT_HOME/.venv/bin/python" -m unittest discover \
  -s factorio-pilot/tools -p 'test_*.py'
```

To rebuild, choose an unused output directory. The builder refuses an existing release:

```bash
"$FACTORIO_PILOT_HOME/.venv/bin/python" factorio-pilot/tools/a06_dataset.py build \
  --tokenizer-snapshot "$TOKENIZER_SNAPSHOT" \
  --output factorio-pilot/evidence/datasets/A06-scripted-train-new-release
"$FACTORIO_PILOT_HOME/.venv/bin/python" scripts/verify_a06_dataset.py \
  --tokenizer-snapshot "$TOKENIZER_SNAPSHOT" \
  --release A06-scripted-train-new-release
```

The full CPU suite passed **49 tests**, including eight new visibility, chronology, action, trimming, masking and partition checks. Frozen protocol and historical agent/kernel evidence remain unchanged. No native source, game save, inference dependency or GPU setting was changed for this dataset stage.

## Next experiment

Probe QLoRA compatibility and memory fit in a separate environment, then record training dependencies and hyperparameters. Training uses original autograd-capable operators; the forward-only custom RMSNorm kernel is excluded. A smoke adapter must be compared against unchanged 4-bit Qwen under the same renderer and fixtures, with validation-based checkpoint selection and locked held-out evaluation. The current release supports a bounded training experiment, not a broad gameplay or generalization claim.
