# Low drill fuel fixture control

The first A06 training fixture passed its environment checks. The scripted controller maintained production for 20 game minutes, making 375 new iron plates with no failed actions. An idle controller failed after two game minutes, with minute outputs of 5 and 0. Both controls began from the same native save and an exactly matching physical snapshot. These are environment controls, not Qwen results or training examples.

## Methods and results

The [A06 protocol](A06%20-%20Qwen%20Fine%20Tuning%20-%20Protocol.md) assigns `train_drill` to training. After a verified warm-up, preparation set the drill to zero stored coal and 1,000,000 joules in its burning coal, the furnace to three stored coal and 3,000,000 burning joules, the furnace output to 20 plates, and the actor's reserve to 400 coal. Carried plates and chest plates were zero. Preloaded and warm-up plates were excluded by setting the measurement origin after preparation.

The server was Factorio 2.0.73. Controls used the existing validated maintenance tools, a maximum refill of three coal, a 100-plate carrying limit, automatic observations and fixed 900-tick decisions. Production was measured in exact 3,600-tick windows; two consecutive windows below 16 new plates ended the episode. The scripted policy is the A05 reference policy: maintain low stored fuel, then store carried plates, collect near-full output, or wait. Scripted and idle controls run sequentially; no model, training or GPU operation runs in this check.

| Control | Endpoint | Game seconds | Decisions | New plates | Failed actions | Episode wall seconds |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Scripted | Survived 20-minute horizon | 1200 | 80 | 375 | 0 | 167.47 |
| Idle | Sustained production failure | 120 | 8 | 5 | 0 | 16.70 |

Every scripted minute produced 18 or 19 plates. Its trace recorded 420 newly mined ore and 375 newly consumed ore without any manual ore insertion, demonstrating that the operating drill replenished the furnace automatically beyond its initial input inventory. Wall time starts after restoring the fixture and excludes construction, warm-up, saving, server restarts and tool reloading. It is not total setup time or model response latency.

At idle termination, the drill had no stored coal or burning energy and reported `NO_FUEL`. The furnace reported `NO_INGREDIENTS`, retained three coal and 1,627,500 burning joules, and had 75 free output slots. The actor still held 400 coal. This failure exposes missed drill refueling rather than reserve depletion or full plate storage.

## Saving and restoration

The native Factorio save is 1,086,584 bytes, with SHA-256 `2af9c4226846876d83f228d0f2400ba6bf0b7b1e5b00b5bd1a272f0c75b917a2`. Its ZIP integrity check passed. The binary remains in external runtime storage at the relative location recorded by [native save metadata](../factorio-pilot/evidence/runs/A06-train_drill-controls-20261006T211921Z/native_save.json); it is not bundled in Git. Reproduction creates a new save. Its binary hash may differ; the prescribed readback and restore checks must still pass.

FLE's entity export omits machine production progress, and its burning-item getter differs from a plain name string. Native saving initially failed because FLE stores executable Lua helpers in persistent game storage. Automatic approval review rejected recursively deleting functions from all storage because the scope and restore path were uncertain. The accepted bounded preparation inventories all functions and verifies that `storage.actions` and `storage.utils` contain only functions, then moves those two tables and four specifically named FLE helpers into a retained runtime backup. Other storage fields remain untouched. The physical snapshot is compared before and after preparation.

After native map loading, the helpers are reconstructed from the installed FLE sources without calling `FactorioInstance.initialise`, which would destroy and recreate the saved actor. The controller explicitly closes and reconnects its RCON socket. Before either control, it requires exact equality of tick, pause state, actor position and full inventory, entity direction/status, stored coal, burning energy, burning item, burner heat, drill mining progress/drop position, furnace crafting progress/products finished/input inventory, and plate counts/capacities. [Scripted restore](../factorio-pilot/evidence/runs/A06-train_drill-controls-20261006T211921Z/scripted_restore.json) and [idle restore](../factorio-pilot/evidence/runs/A06-train_drill-controls-20261006T211921Z/idle_restore.json) both passed. The test server's original scenario command was restored afterward; the original compose file was not edited.

## Evidence and exclusions

[Completed control record](../factorio-pilot/evidence/runs/A06-train_drill-controls-20261006T211921Z/) retains configuration, initial snapshot, both traces and summaries, restore receipts, source snapshots and export hashes. Its [preparation record](../factorio-pilot/evidence/runs/A06-train_drill-controls-20261006T211921Z/preparation/) preserves the source and settings used to create the native fixture in `A06-train_drill-controls-20261006T211313Z`. The completed run resumes that save, rather than constructing a different starting factory.

Earlier setup attempts remain in external runtime storage and are excluded from gameplay scores: `20261006T210558Z` rejected removal of zero items from an empty inventory; `20261006T210659Z` and `20261006T210835Z` stopped on burning-item name readback; `20261006T210955Z` reached native saving but Factorio rejected unserializable helper functions; `20261006T211313Z` created the retained native save but its first control stopped on a stale RCON socket before gameplay. A raw RCON helper command with a newline immediately after `/sc` was rejected before changing storage and was corrected. No failed setup attempt is relabeled as a model failure or a passed control.

All five project-authored native sources were inspected; the unchanged exact-hash gate passed. Forty CPU tests passed, including four fixture readback/policy tests. The portable audit checks export bytes, protocol/source hashes, both restored snapshots, all 88 decision intervals, minute production deltas, and plate conservation across every decision and successful transfer. No sanitizer or GPU setting was changed. The initial export manifest is retained alongside the extended manifest containing preparation evidence.

This validates one of nine recipes. The other eight still need controls. No dataset release, compact Qwen renderer, QLoRA memory probe or trained adapter exists yet. The successful trace may become a data source only after the shared input renderer and dataset checks satisfy A06; it is not already an audited training dataset.

## Reproduction

Use the [pinned runtime](../factorio-pilot/README.md), with the source checkout on the Linux filesystem or mounted into WSL. The helper tools depend on the recorded FLE environment, `factorio-rcon-py` and PyYAML 6.0.3. Use one server and two terminals because the controller waits at explicit save/load barriers. Run the controller as the ordinary Linux user; only Docker/save-directory orchestration needs elevated access. Keep the WSL controller process open across server restarts.

From the repository root, terminal A:

```bash
export FACTORIO_PILOT_HOME="${FACTORIO_PILOT_HOME:-$HOME/factorio-pilot}"
sudo docker start cluster-factorio_0-1
sudo docker exec -u root cluster-factorio_0-1 install -d -o 845 -g 845 -m 755 /factorio/saves
"$FACTORIO_PILOT_HOME/.venv/bin/python" -u factorio-pilot/tools/a06_fixture_controls.py --fixture train_drill
```

At `SAVE_HELPER_INSPECTION_REQUIRED`, terminal B sets the run basename printed by terminal A:

```bash
export FACTORIO_PILOT_HOME="${FACTORIO_PILOT_HOME:-$HOME/factorio-pilot}"
export A06_RUN_NAME="A06-train_drill-controls-YYYYMMDDTHHMMSSZ"
"$FACTORIO_PILOT_HOME/.venv/bin/python" factorio-pilot/tools/a06_save_helpers.py prepare --run "$FACTORIO_PILOT_HOME/runs/$A06_RUN_NAME"
```

After preparation passes, type `SAVE` in terminal A. Wait for `RESTORE_REQUIRED scripted` and note its `NATIVE_SAVE` basename. In terminal B:

```bash
export A06_SAVE_NAME="a06_train_drill_YYYYMMDDTHHMMSSZ.zip"
sudo "$FACTORIO_PILOT_HOME/.venv/bin/python" factorio-pilot/tools/a06_native_server.py capture-and-restore --runtime-home "$FACTORIO_PILOT_HOME" --owner "$(id -un)" --run-name "$A06_RUN_NAME" --save-name "$A06_SAVE_NAME"
"$FACTORIO_PILOT_HOME/.venv/bin/python" factorio-pilot/tools/a06_save_helpers.py restore --run "$FACTORIO_PILOT_HOME/runs/$A06_RUN_NAME"
```

Type `RESTORED` in terminal A after helper restoration passes. At `RESTORE_REQUIRED idle`, repeat the native-server command with `restore` instead of `capture-and-restore` and omit `--save-name`; rerun the helper `restore`, then type `RESTORED` again. Require `FIXTURE_CONTROL_PASS`. Restore the default server command with:

```bash
sudo "$FACTORIO_PILOT_HOME/.venv/bin/python" factorio-pilot/tools/a06_native_server.py default --runtime-home "$FACTORIO_PILOT_HOME" --owner "$(id -un)"
```

For portable inspection of the retained result, without Factorio or a GPU:

```bash
python scripts/verify_a06_controls.py A06-train_drill-controls-20261006T211921Z
```

The exporter is `scripts/package_a06_controls.py --run <completed-runtime-run> --repo <checkout>`. It supports fresh controls and resumed native-save provenance, preserves preparation sources, and refuses to overwrite an existing export. The measured record used `--resume-run` after the connection fix.
