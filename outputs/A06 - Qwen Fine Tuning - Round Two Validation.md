# A06 — Round two validation

The frozen rule selected checkpoint 20 after both checkpoints completed both validation factories. These fixtures select checkpoints; they are not the final test set. Round three and final comparisons remain pending.

| Condition | Factory | Capped survival (seconds) | New plates | Failed actions |
|---|---|---:|---:|---:|
| unchanged 4-bit | validation_fuel | 1200 | 327 | 7 |
| unchanged 4-bit | validation_storage | 1200 | 353 | 1 |
| round two checkpoint-20 | validation_fuel | 1200 | 371 | 0 |
| round two checkpoint-20 | validation_storage | 1200 | 375 | 0 |
| round two checkpoint-40 | validation_fuel | 1200 | 371 | 1 |
| round two checkpoint-40 | validation_storage | 1200 | 375 | 1 |

Selection compares mean survival, then total new plates, then the earlier checkpoint. Failed actions are reported separately and are not an extra selection criterion. Survival through 1,200 seconds is capped survival, not evidence of indefinite reliability.

The matched comparisons use the same quantization, fixture, simulation cadence, tools, guide, decoding and evaluated source hashes. Absolute plate differences are validation_fuel: +44, validation_storage: +22. These two single-seed validation comparisons do not establish general Factorio competence or final-test improvement.

## Waiting interpretation

Checkpoint 20 made 46 waits on the fuel factory and 42 on the storage factory while both reached the production horizon. The predefined diagnostic marked 40 and 25 of those waits as maintenance opportunities. A flag can indicate carried stock or equipment needing attention soon; it does not prove an urgent intervention was missed. Preserve the heuristic and interpret it alongside actual production, storage, fuel and executed repairs. Do not conclude that fewer waits always means better gameplay.

## Evidence

[Summaries, source receipts, selection scores and matched checks](../factorio-pilot/evidence/artifacts/A06-round2-validation.json) preserve both candidates. [Training curves](../factorio-pilot/evidence/artifacts/A06-round2-training/receipt.json) remain separate from gameplay evidence. The selected adapter next plays training factories; only their verified corrections may feed round three.
