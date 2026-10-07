# Nine fixture control results

All nine frozen A06 recipes now have passing executed reachability controls, idle controls, verified presets and exact saved-state restores. These are CPU environment checks, not Qwen evaluation or a training dataset. The four train recipes, two validation recipes and three test recipes retain their original partitions and hashes.

## Measured results

Each passing scripted control survived twenty game minutes and produced 375 new iron plates with zero failed tool calls. Every minute produced eighteen or nineteen new plates, above the threshold of sixteen. Idle ended after two or three game minutes under the unchanged rule: two consecutive low windows.

| Fixture | Partition | New scripted plates | Idle minute outputs | Idle game minutes | Evidence |
| --- | --- | ---: | --- | ---: | --- |
| train_drill | train | 375 | 5, 0 | 2 | [Trace](../factorio-pilot/evidence/runs/A06-train_drill-controls-20261006T211921Z/) |
| train_furnace | train | 375 | 3, 0 | 2 | [Trace](../factorio-pilot/evidence/runs/A06-train_furnace-controls-20261006T223803Z/) |
| train_output | train | 375 | 10, 0 | 2 | [Trace](../factorio-pilot/evidence/runs/A06-train_output-controls-20261007T022345Z/) |
| train_carry | train | 375 | 10, 0 | 2 | [Trace](../factorio-pilot/evidence/runs/A06-train_carry-controls-20261007T022727Z/) |
| validation_fuel | validation | 375 | 10, 0 | 2 | [Trace](../factorio-pilot/evidence/runs/A06-validation_fuel-controls-20261007T023116Z/) |
| validation_storage | validation | 375 | 5, 0 | 2 | [Trace](../factorio-pilot/evidence/runs/A06-validation_storage-controls-20261007T023455Z/) |
| test_drill_storage | test | 375 | 11, 0 | 2 | [Trace](../factorio-pilot/evidence/runs/A06-test_drill_storage-controls-20261007T023821Z/) |
| test_furnace_output | test | 375 | 2, 0 | 2 | [Trace](../factorio-pilot/evidence/runs/A06-test_furnace_output-controls-20261007T025317Z/) |
| test_reserve_storage | test | 375 | 18, 0, 0 | 3 | [Trace](../factorio-pilot/evidence/runs/A06-test_reserve_storage-controls-20261007T024515Z/) |

The scripts observe, execute one allowed action and advance exactly 900 ticks (fifteen game seconds). Each four decisions forms a 3,600-tick production window. Setup construction, sixty-second warm-up, preloaded plates and server restarts are excluded from new production. Burning coal energy and stored coal are separate verified presets. The world pauses between decisions; game speed ten accelerates simulation. No GPU or model inference ran.

The [protocol](A06%20-%20Qwen%20Fine%20Tuning%20-%20Protocol.md) is unchanged. The [portable completeness audit](../scripts/verify_a06_fixture_suite.py) requires all nine registered recipes, verifies actual presets, warm-up output, capacities, common geometry, source/export hashes, exact restores, every logged decision interval and plate conservation. The [host completion receipt](../factorio-pilot/evidence/artifacts/A06-fixture-suite-complete.json) additionally verifies each external native ZIP's bytes, SHA-256 and ZIP integrity. Masters remain outside Git.

## What went wrong and what changed

The legacy fuel-first reference did not pass the strict control checkpoint on `test_furnace_output`. Its first four actions were furnace refuel, store carried plates, drill refuel and collect furnace output. Output was full at the first three fifteen-second observations. The first minute produced seven plates. Later windows recovered and the episode survived twenty minutes, producing 363 plates overall, but survival did not erase that initial below-target window. The [rejected run](../factorio-pilot/evidence/runs/A06-test_furnace_output-controls-20261007T024151Z/) and its [audit](../factorio-pilot/evidence/artifacts/A06-rejected-reference-audit.json) are retained; the normal verifier rejects it as reachability evidence.

A separately named `congestion-control` prioritizes collection when output is at least 95 plates and carrying space remains, or storage when carrying is full. Otherwise it uses the existing reference. The replay loaded the exact original native save, preserving tick, progress, inventories and energy. Its first minute produced eighteen plates, and every subsequent minute met target. This establishes a viable action ordering for that recipe without changing its starting conditions or relaxing the threshold. The default A05 train teacher is unchanged. The alternate mode is rejected on non-test fixtures, and these test control traces are excluded from optimizer examples, retrieval, prompt hints and checkpoint selection.

Replay attempt `A06-test_furnace_output-controls-20261007T024936Z` was stopped before gameplay by a native-save hash mismatch and remains in external runtime storage. Investigation found six master files had changed after subsequent setup while directly mounted as writable server saves. Their exact original named archives still existed, including one in a retained Docker volume. All six were restored only from originals matching the original recorded SHA-256; changed files were preserved separately. [Recovery receipt](../factorio-pilot/evidence/artifacts/A06-save-recovery.json) records both hashes and recovery sources. No recorded hash was replaced with a new value. The precise engine/setup save operation was not isolated; the writable master mount was the confirmed storage defect.

`a06_native_server.py` now creates a fresh disposable working directory for each restore and copies the hash-checked master there. The server mounts that working directory, leaving the master outside its writable save path. [Live Docker inspection](../factorio-pilot/evidence/artifacts/A06-working-mount-check.json) confirms the actual mount. Load receipts preserve working-copy hashes and the exact orchestration source. The corrected replay passed both exact physical restores; all nine master archives were checked again after completion. Prior physical restore receipts and action traces remain unchanged. The default server command was restored afterward.

## Interpretation and limits

These controls demonstrate that the fixed tasks are solvable, can fail through neglect and can be measured consistently. They do not demonstrate Qwen's understanding, fine-tuning improvement, an optimal policy or indefinite factory survival. The recipes share one layout and primarily vary fuel, carried plates, output and chest inventories. One deterministic control per recipe gives reachability evidence, not independent model-performance statistics.

For the output case, ninety preloaded plates left ten available slots: idle made ten new plates and then zero. The furnace first reported full output at the forty-five-second observation while the drill still worked. The near-full output recipe therefore supplies an observed storage bottleneck. In the low-furnace-fuel control, the furnace first lacked fuel at fifteen seconds while the drill still worked. In the small-reserve fixture, idle passed one window before failing two in succession; its three-minute endpoint follows the detection rule, rather than a universal two-minute failure assumption. Inspect the time series to identify the first bottleneck, not just the final state.

Forty-one CPU tests passed, including the alternate-control regression that preserves default behavior and obeys carrying capacity. The native exact-hash gate passed; no authored C++/CUDA source or GPU setting changed. Historical maintenance and K02 evidence audits still pass. No training environment or dependency was changed.

## Reproduction and next work

The manual barriers remain available in the [first fixture report](A06%20-%20Qwen%20Fine%20Tuning%20-%20Fixture%20Control.md#reproduction). The new supervisor automates them sequentially with an ordinary-user controller and elevated Docker orchestration. Use the pinned external environment, a single server and the intended checkout. It records control logs and source snapshots, verifies RCON readiness, retains rejected endpoints and restores the default server command.

```bash
sudo "$FACTORIO_PILOT_HOME/.venv/bin/python" factorio-pilot/tools/a06_control_batch.py \
  --runtime-home "$FACTORIO_PILOT_HOME" --owner "$(id -un)" \
  --fixtures train_output train_carry validation_fuel validation_storage \
  test_drill_storage test_furnace_output test_reserve_storage
```

For the test-only replay, select only `test_furnace_output`, pass `--resume-run` with its original runtime run path, and `--reference-policy congestion-control`. A fresh run is a new experiment with new receipts; never overwrite retained evidence. `package_a06_controls.py --include-rejected-control` explicitly archives rejected controls, while `verify_a06_controls.py --allow-rejected-control` audits their integrity without labeling them a validated fixture. Defaults still require reachability.

```bash
python scripts/verify_a06_fixture_suite.py
```

Next comes the common compact input renderer and a dataset builder that retains episode lineages, filters private information, masks loss to the target action and rejects validation/test optimizer rows. Data still needs semantic-duplicate and label-execution audits. QLoRA compatibility/memory checks, training and matched unchanged-model comparisons are subsequent work.
