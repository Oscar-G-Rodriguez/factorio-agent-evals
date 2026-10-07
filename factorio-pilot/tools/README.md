# Tool map

The current maintenance study starts with `maintenance_agent.py`. It uses `maintenance_tools.py` and the shared game, factory, and logistics bridges. The earlier construction runner is `run_agent.py`; guided construction and logistics use `working_agent.py`. Each stage has its own saved configuration and evaluated source snapshot in `../evidence/` and `../source-snapshots/`.

`observation_policy.py` filters model-visible feedback and timestamps snapshots for the explicit A05 automatic/requested modes. `test_observation_policy.py` checks that private state cannot leak between inspections. The legacy A04 prompt path remains the default.

The other files support these runs:

| Purpose | Files |
| --- | --- |
| Setup and environment checks | `prepare_cluster.py`, `download_model.py`, `check_environment.py`, `check_game.py`, `check_model.py`, `check_logistics.py` |
| Native review and measurements | `cuda_review.py`, `check_rmsnorm.py`, `benchmark_reference.py`, `profile_model.py`, `qwen_rmsnorm_backend.py`, `check_integrated_rmsnorm.py` |
| Evidence and reports | `export_evidence.py`, `report_pilot.py`, `report_working_agent.py`, `audit_working_agent.py`, `summarize_runs.py`, `show_progress.py`, `probe_storage_context.py` |
| CPU checks | `test_*.py` |
| Shared runtime path | `runtime_paths.py`; set `FACTORIO_PILOT_HOME` to the Linux directory containing `.venv`, `artifacts`, `runs`, and `cluster` |

The [legacy folder](legacy/README.md) holds one-off development helpers that are not part of the supported run sequence. Historical source snapshots remain under `../source-snapshots/` and are never moved here.

## A06 fixture controls

`a06_fixture_controls.py` accepts the frozen registry fixture IDs, verifies post-warm-up presets and executes separate scripted and idle controls with exact native-state checks. `a06_save_helpers.py` and `a06_native_server.py` handle bounded helper preparation and external save restoration. Follow the explicit barriers and two-terminal sequence in the [fixture control report](../../outputs/A06%20-%20Qwen%20Fine%20Tuning%20-%20Fixture%20Control.md). The game ZIP stays outside Git. All nine recipes have verified controls. `a06_control_batch.py` automates the save/restore barriers sequentially. Native loading uses disposable working copies rather than mounting master archives. `--reference-policy congestion-control` is test-only and excluded from optimizer data; the default train teacher remains unchanged. `test_a06_fixture_controls.py` checks readback and reference-policy decisions without running the game.

## A06 context and dataset

`a06_context.py` owns compact observed-state projection, chronological two-pair history, token trimming and target-only loss masking. `a06_dataset.py` renders the four executed train traces, records evidence and hashes, audits immutable releases and rejects reserved fixtures at the optimizer boundary. `load_optimizer_dataset` audits before returning encodings. `test_a06_context.py` covers visibility, chronology, capacities, handles, trimming, masking and partition isolation. The [dataset audit](../../outputs/A06%20-%20Qwen%20Fine%20Tuning%20-%20Dataset%20Audit.md) gives exact commands; `scripts/verify_a06_dataset.py` verifies the pinned-tokenizer release on CPU. No game, model or GPU is loaded.
