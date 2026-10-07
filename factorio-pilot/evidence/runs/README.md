# Saved Factorio runs

This directory retains 21 original agent run records, three later A05 observation-policy episodes two K02 offline inference records and nine validated A06 fixture-control groups and one rejected reference group. Folder names now connect each record to the experiment stages used by the [result reports](../../../README.md). No configuration, action trace, summary, or final-state file was edited during the rename.

## Folder names

Use `A##-<condition>-<YYYYMMDDTHHMMSSZ>[-seedN]` for new Factorio agent runs. `A##` matches the report stage; the condition names the controller or experimental mode; the timestamp is the run start in UTC; and the seed suffix is present when the runner records a seed. For example, `A04-maintenance-model-20261006T044058Z` is the model condition in the A04 maintenance stage. A future kernel or integrated-inference run may use the corresponding `K##-<condition>-<UTC timestamp>[-seedN]` form. Do not reuse a folder name or add an outcome such as `success` to it after the run.

The existing folders keep their original runtime IDs after the stage prefix. Some saved JSON fields and source logs still use those original IDs; remove `A##-` from a folder name to match them. Those values are historical evidence, not misplaced files. Several early runs are partial or excluded from the reported comparison. A `summary.json` means the run completed enough to save a summary; it does not by itself make the run a scored result.

| Stage | Saved folders | Reported comparison |
| --- | ---: | --- |
| A01 — original construction and context pilot | 14, including four partial records | The final comparison uses `A01-baseline-20261006T015013Z-seed42`, `A01-baseline-20261006T015320Z-seed42`, `A01-intervention-20261006T015125Z-seed42`, and `A01-intervention-20261006T015904Z-seed42`. See the [A01 final report](../../../outputs/A01%20-%20Construction%20Pilot%20-%20Final%20Results.md). |
| A02 — guided construction | 3, including one partial record | `A02-working-development-20261006T025602Z` and `A02-working-development-20261006T030421Z`. See the [A02 report](../../../outputs/A02%20-%20Guided%20Construction%20-%20Results.md). |
| A03 — storage and expansion | 1 | `A03-logistics-development-20261006T035914Z`. See the [A03 report](../../../outputs/A03%20-%20Storage%20and%20Expansion%20-%20Results.md). |
| A04 — maintenance | 3 | `A04-maintenance-idle-20261006T043628Z`, `A04-maintenance-scripted-20261006T043718Z`, and `A04-maintenance-model-20261006T044058Z`. See the [A04 report](../../../outputs/A04%20-%20Maintenance%20-%20Results.md). |

K02 records are `K02-integrated-20261006T082739Z` (initial eager/custom validation) and `K02-integrated-20261006T082927Z` (eager/custom/compiled validation and completed warm timing). Each contains `results.json`, a frozen `prompt-manifest.json`, evaluated Python snapshots and `export-sha256.json`. The latter verifies copied evidence bytes. These records execute inference on saved prompts, not Factorio actions; see the [K02 report](../../../outputs/K02%20-%20RMSNorm%20-%20Integrated%20Inference%20Results.md).

A05 contains `A05-observation-requested-scripted-20261006T181451Z`, `A05-observation-automatic-model-20261006T182130Z` and `A05-observation-requested-model-20261006T182355Z`. Their [pilot report](../../../outputs/A05%20-%20Observation%20Policy%20-%20Pilot%20Results.md) keeps the scripted reachability control separate from the two executed model conditions. Each export retains the evaluated Python files, byte hashes and agent-visible input per step. A fourth attempt failed to connect before gameplay; its ID and exclusion are recorded in the report.

Each agent run's `config.json` records its protocol and evaluated source hashes. `steps.jsonl` holds individual decisions or attempts. Completed runs usually include `summary.json`; construction runs may also include `final-state.json` and an audit. Read the linked report and any quality or development notes before treating a run as comparable evidence. Future runs should keep this folder convention and add their report, configuration, raw trace, and source snapshot without changing older records.

## A06 first fixture control

`A06-train_drill-controls-20261006T211921Z` contains separate `scripted/` and `idle/` traces, exact restore receipts, source snapshots and export hashes. Its `preparation/` folder preserves native fixture preparation from `A06-train_drill-controls-20261006T211313Z`. The [report](../../../outputs/A06%20-%20Qwen%20Fine%20Tuning%20-%20Fixture%20Control.md) records excluded setup attempts and the external save hash. This establishes reachability and failure for one training recipe; it contains no Qwen episode or audited training dataset.

`A06-train_furnace-controls-20261006T223803Z` adds the low-furnace-fuel scripted and idle controls. Its [report](../../../outputs/A06%20-%20Qwen%20Fine%20Tuning%20-%20Furnace%20Fixture%20Control.md) records presets, exact restores, minute windows and excluded setup events. Both A06 groups are environment controls, not Qwen evaluations or training datasets.

The [A06 suite report](../../../outputs/A06%20-%20Qwen%20Fine%20Tuning%20-%20Fixture%20Suite%20Results.md) maps all nine validated groups to their recipes. `A06-test_furnace_output-controls-20261007T024151Z` is a separately retained rejected reference; its first minute missed the strict threshold despite later recovery. A later exact-state congestion-control replay establishes that recipe's reachability. Failed pre-game replay attempts remain outside Git, identified in the report.
