# A06 — Two completed training rounds

Two actual training rounds are complete. Round-two gameplay validation is still running; round three, final tests, and final conclusions remain pending. Training loss measures fit to the labeled actions and does not establish gameplay improvement.

| Round | Updates | Training examples processed | Duration (minutes) | Trainable adapter parameters |
|---|---:|---:|---:|---:|
| 1 | 40 | 320 | 11.05 | 16,515,072 |
| 2 | 40 | 320 | 10.96 | 16,515,072 |

Round one used all 320 original verified examples. Round two continued selected round-one checkpoint 40 with a fresh optimizer, using 160 original rows and 160 sampled corrections from the 13-row verified release. Every round freezes the quantized base model and trains the adapter; gameplay loads one saved adapter and does not update it.

The first round-two checkpoint-20 validation episode reached the 20-minute cap with 371 new plates and zero failed actions. Unchanged 4-bit Qwen reached the same cap on that factory with 327 plates and seven failed actions. This is one validation comparison, not final-test evidence or a complete checkpoint selection.

## Evidence

[Round one curve and training receipt](../factorio-pilot/evidence/artifacts/A06-round1-training/receipt.json), [round two curve and training receipt](../factorio-pilot/evidence/artifacts/A06-round2-training/receipt.json), and [corrective data results](A06%20-%20Qwen%20Fine%20Tuning%20-%20Round%20One%20Corrections.md) preserve the counts and measured training durations. Checkpoints 20 and 40 remain the only selection candidates; the selected adapter will be evaluated on training factories before corrections for round three are collected.
