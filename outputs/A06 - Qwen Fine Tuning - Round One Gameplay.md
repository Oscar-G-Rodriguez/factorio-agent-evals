# A06 — Round one gameplay

Round one completed 40 updates, but its selected adapter performed worse than unchanged 4-bit Qwen on both validation factories. Lower training loss did not establish gameplay improvement. These are validation and training diagnostics; the reserved final test factories remain unopened.

| Factory | Unchanged survival (seconds) | Round one survival (seconds) | Unchanged new plates | Round one new plates |
|---|---:|---:|---:|---:|
| train_drill | 360 | 360 | 80 | 80 |
| train_furnace | 1140 | 360 | 312 | 80 |
| train_output | 540 | 120 | 149 | 10 |
| train_carry | 120 | 120 | 10 | 10 |
| validation_fuel | 1200 | 300 | 327 | 70 |
| validation_storage | 1200 | 120 | 353 | 5 |

Unchanged validation survival reached the 1,200-second cap on both factories. Round one checkpoint 20 averaged 120 seconds with 15 combined new plates; checkpoint 40 averaged 210 seconds with 75 combined new plates. The frozen selection rule therefore selected checkpoint 40, although both candidates were worse than the baseline.

Checkpoint 40 used fuel and wait actions on the fuel validation factory; on the storage validation factory it left 100 carried plates and a full furnace while the chest still had capacity. This supports a missed storage intervention as a failure mechanism in that episode. Waiting flags alone are diagnostic heuristics, not proof that compute or training caused every failure.

Verified corrections are being replayed from exact pre-action states of training factories. Round two may start only after at least eight distinct corrections across two factories pass execution and full-horizon continuation checks.

## Evidence

[Episode summaries, source receipts, and checkpoint selection](../factorio-pilot/evidence/artifacts/A06-round1-gameplay.json). Full traces remain in the external runtime until final evidence packaging.

Training loss, duration, and peak memory are recorded separately in [round one training evidence](../factorio-pilot/evidence/artifacts/A06-round1-training/summary.json). This result supports no resume claim of model improvement.
