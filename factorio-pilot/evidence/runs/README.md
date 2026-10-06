# Saved Factorio runs

This directory retains 21 original run records. Folder names now connect each record to the experiment stages used by the [result reports](../../../README.md). No configuration, action trace, summary, or final-state file was edited during the rename.

## Folder names

Use `A##-<condition>-<YYYYMMDDTHHMMSSZ>[-seedN]` for new Factorio agent runs. `A##` matches the report stage; the condition names the controller or experimental mode; the timestamp is the run start in UTC; and the seed suffix is present when the runner records a seed. For example, `A04-maintenance-model-20261006T044058Z` is the model condition in the A04 maintenance stage. A future kernel or integrated-inference run may use the corresponding `K##-<condition>-<UTC timestamp>[-seedN]` form. Do not reuse a folder name or add an outcome such as `success` to it after the run.

The existing folders keep their original runtime IDs after the stage prefix. Some saved JSON fields and source logs still use those original IDs; remove `A##-` from a folder name to match them. Those values are historical evidence, not misplaced files. Several early runs are partial or excluded from the reported comparison. A `summary.json` means the run completed enough to save a summary; it does not by itself make the run a scored result.

| Stage | Saved folders | Reported comparison |
| --- | ---: | --- |
| A01 — original construction and context pilot | 14, including four partial records | The final comparison uses `A01-baseline-20261006T015013Z-seed42`, `A01-baseline-20261006T015320Z-seed42`, `A01-intervention-20261006T015125Z-seed42`, and `A01-intervention-20261006T015904Z-seed42`. See the [A01 final report](../../../outputs/A01%20-%20Construction%20Pilot%20-%20Final%20Results.md). |
| A02 — guided construction | 3, including one partial record | `A02-working-development-20261006T025602Z` and `A02-working-development-20261006T030421Z`. See the [A02 report](../../../outputs/A02%20-%20Guided%20Construction%20-%20Results.md). |
| A03 — storage and expansion | 1 | `A03-logistics-development-20261006T035914Z`. See the [A03 report](../../../outputs/A03%20-%20Storage%20and%20Expansion%20-%20Results.md). |
| A04 — maintenance | 3 | `A04-maintenance-idle-20261006T043628Z`, `A04-maintenance-scripted-20261006T043718Z`, and `A04-maintenance-model-20261006T044058Z`. See the [A04 report](../../../outputs/A04%20-%20Maintenance%20-%20Results.md). |

Each run's `config.json` records its protocol and evaluated source hashes. `steps.jsonl` holds individual decisions or attempts. Completed runs usually include `summary.json`; construction runs may also include `final-state.json` and an audit. Read the linked report and any quality or development notes before treating a run as comparable evidence. Future runs should keep this folder convention and add their report, configuration, raw trace, and source snapshot without changing older records.
