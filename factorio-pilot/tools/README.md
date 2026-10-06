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
