# A06 — Round two training-factory diagnostics

The selected round-two adapter completed all four training-factory episodes through the 20-minute cap. The frozen candidate rule identified only five distinct eligible proposals across three factories. Even if all five pass exact-state replay, they cannot meet the required eight-row gate for round three. Verification is running; no third training round or final test is claimed.

| Factory | Unchanged new plates | Round one new plates | Round two new plates | Round two failed actions |
|---|---:|---:|---:|---:|
| train_drill | 80 | 80 | 374 | 1 |
| train_furnace | 312 | 80 | 375 | 0 |
| train_output | 149 | 10 | 375 | 1 |
| train_carry | 10 | 10 | 373 | 0 |

These are training factories and cannot support a held-out generalization claim. Round two made two failed actions in total, both attempts to store plates while carrying none. The five proposals comprise two blocked-transfer corrections and three fuel-neglect corrections. They must still execute successfully from saved pre-action states and retain the original full-horizon production requirement.

The agreed stop rule forbids manufacturing corrections, reusing validation/test labels, or presenting another identical-data pass as a corrective training round. Preserve the two trained adapters, all candidates, and the unopened final test set. Continuing beyond this gate would require an explicitly revised protocol.

## Evidence

[Episode summaries, hashes and candidate receipts](../factorio-pilot/evidence/artifacts/A06-round2-training-diagnostics.json) retain all three model conditions on the training fixtures. [Round two validation](A06%20-%20Qwen%20Fine%20Tuning%20-%20Round%20Two%20Validation.md) is separate and records checkpoint selection. Verification outcomes and final packaging remain pending.
